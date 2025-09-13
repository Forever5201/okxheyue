import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from src.logger import setup_logger
import time
import hmac
import base64
import hashlib
import pandas as pd

logger = setup_logger()

class DataFetcher:
    def __init__(self, api_key, secret_key, passphrase, base_url="https://www.okx.com"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.base_url = base_url
        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

    def _get_headers(self, method, path, body):
        timestamp = str(time.time())
        pre_hash_string = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"), pre_hash_string.encode("utf-8"), hashlib.sha256
        ).digest()
        signature_base64 = base64.b64encode(signature).decode()

        headers = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature_base64,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase
        }
        return headers

    def fetch_funding_rate(self, instrument_id):
        """获取资金费率信息，添加空值处理"""
        endpoint = "/api/v5/public/funding-rate"
        params = {"instId": instrument_id}
        headers = self._get_headers("GET", endpoint, "")
        
        try:
            logger.info(f"Fetching funding rate for {instrument_id}...")
            response = self.session.get(f"{self.base_url}{endpoint}", headers=headers, params=params)
            response.raise_for_status()
            data = response.json().get("data", [])
            
            if data and len(data) > 0:
                funding_data = data[0]
                return {
                    "funding_rate": float(funding_data.get("fundingRate") or 0),
                    "next_funding_time": funding_data.get("nextFundingTime", ""),
                    "estimated_rate": float(funding_data.get("nextFundingRate") or 0)
                }
            return {
                "funding_rate": 0,
                "next_funding_time": "",
                "estimated_rate": 0
            }
        except Exception as e:
            logger.error(f"Error fetching funding rate: {e}")
            return {
                "funding_rate": 0,
                "next_funding_time": "",
                "estimated_rate": 0
            }

    def _process_kline_data(self, df):
        """处理K线数据的公共方法"""
        try:
            numeric_columns = ["open", "high", "low", "close", "volume", 
                             "currency_volume", "turnover"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            
            if "trades" in df.columns:
                df["trades"] = df["trades"].astype(int, errors="ignore")

            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), 
                                           unit="ms", utc=True)
            df["time_iso"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            df["timestamp"] = df["timestamp"].astype(int) // 10**6

            df["ohlc"] = df.apply(lambda row: {
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"]
            }, axis=1)

            return df.where(pd.notna(df), None)
        except Exception as e:
            logger.error(f"Error processing kline data: {e}")
            return df

    def get_current_kline(self, instrument_id, bar):
        """获取当前未完结的K线数据"""
        endpoint = "/api/v5/market/candles"
        params = {"instId": instrument_id, "bar": bar, "limit": 1}
        headers = self._get_headers("GET", endpoint, "")
        
        try:
            logger.info(f"Fetching current k-line for {instrument_id} at {bar}...")
            response = self.session.get(f"{self.base_url}{endpoint}", 
                                     headers=headers, 
                                     params=params)
            response.raise_for_status()
            data = response.json().get("data", [])
            
            if data:
                columns = ["timestamp", "open", "high", "low", "close", "volume", 
                          "currency_volume", "turnover", "trades"]
                df = pd.DataFrame([data[0]], columns=columns)
                df = self._process_kline_data(df)
                funding_data = self.fetch_funding_rate(instrument_id)
                df["funding_rate"] = funding_data.get("funding_rate", 0)
                df["is_closed"] = False
                logger.info("Successfully fetched current k-line.")
                return df
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error fetching current kline: {e}")
            return pd.DataFrame()

    def fetch_market_tickers(self, instrument_id):
        """获取市场数据"""
        endpoint = "/api/v5/market/ticker"
        params = {"instId": instrument_id}
        headers = self._get_headers("GET", endpoint, "")
        try:
            logger.info(f"Fetching market tickers for {instrument_id}...")
            response = self.session.get(f"{self.base_url}{endpoint}", 
                                     headers=headers, 
                                     params=params)
            response.raise_for_status()
            data = response.json().get("data", [])
            
            if data and len(data) > 0:
                ticker = data[0]
                funding_data = self.fetch_funding_rate(instrument_id)
                return {
                    "last_price": float(ticker.get("last") or 0),
                    "best_bid": float(ticker.get("bidPx") or 0),
                    "best_ask": float(ticker.get("askPx") or 0),
                    "24h_high": float(ticker.get("high24h") or 0),
                    "24h_low": float(ticker.get("low24h") or 0),
                    "24h_volume": float(ticker.get("vol24h") or 0),
                    "24h_turnover": float(ticker.get("volCcy24h") or 0),
                    "open_interest": float(ticker.get("openInt") or 0),
                    "funding_rate": funding_data.get("funding_rate", 0),
                    "next_funding_time": funding_data.get("next_funding_time", ""),
                    "estimated_rate": funding_data.get("estimated_rate", 0),
                    "timestamp": int(time.time() * 1000),
                    "time_iso": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                }
            return {}
        except Exception as e:
            logger.error(f"Error fetching market tickers: {e}")
            return {}

    # 保持兼容性的方法
    def fetch_ticker(self, instrument_id):
        """保持与旧代码的兼容性"""
        return self.fetch_market_tickers(instrument_id)

    def fetch_kline_data(self, instrument_id, bar, is_mark_price=True, limit=100):
        if is_mark_price:
            return self.fetch_mark_price_kline(instrument_id, bar, limit)
        else:
            return self.fetch_actual_price_kline(instrument_id, bar, limit)

    def fetch_mark_price_kline(self, instrument_id, bar, limit=100):
        columns = ["timestamp", "open", "high", "low", "close", "volume", 
                  "currency_volume", "turnover", "trades"]
        return self._fetch_kline_data("/api/v5/market/mark-price-candles", 
                                    instrument_id, bar, limit, columns)

    def fetch_actual_price_kline(self, instrument_id, bar, limit=100):
        columns = ["timestamp", "open", "high", "low", "close", "volume", 
                  "currency_volume", "turnover", "trades"]
        df = self._fetch_kline_data("/api/v5/market/candles", instrument_id, bar, limit, columns)
        
        # 添加资金费率信息
        if not df.empty:
            funding_data = self.fetch_funding_rate(instrument_id)
            df["funding_rate"] = funding_data.get("funding_rate", 0)
        
        return df

    def _fetch_kline_data(self, endpoint, instrument_id, bar, limit, columns):
        params = {"instId": instrument_id, "bar": bar, "limit": limit}
        headers = self._get_headers("GET", endpoint, "")
        try:
            logger.info(f"Fetching K-line data from {endpoint} ({limit} points) for {instrument_id} at {bar}...")
            response = self.session.get(self.base_url + endpoint, headers=headers, params=params)
            response.raise_for_status()
            raw_data = response.json().get("data", [])

            if not raw_data:
                logger.warning("No K-line data returned.")
                return pd.DataFrame()

            if len(raw_data[0]) != len(columns):
                logger.warning(f"Column mismatch. Adjusting...")
                columns = columns[:len(raw_data[0])]

            df = pd.DataFrame(raw_data, columns=columns)
            df = self._process_kline_data(df)
            df["is_closed"] = True
            
            logger.info(f"Fetched {len(df)} K-line data.")
            return df

        except Exception as e:
            logger.error(f"Error fetching K-line data: {e}", exc_info=True)
            return pd.DataFrame()