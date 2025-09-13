import pandas as pd
import numpy as np
from src.logger import setup_logger
try:
    import pandas_ta as ta  # type: ignore
except Exception:
    ta = None

logger = setup_logger()


class RSIIndicator:
    def __init__(self, close, window):
        self.close = close
        self.window = window

    def rsi(self):
        try:
            delta = self.close.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=self.window, min_periods=1).mean()
            avg_loss = loss.rolling(window=self.window, min_periods=1).mean()
            rs = avg_gain / avg_loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            return rsi.fillna(0)
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return pd.Series(np.nan, index=self.close.index)


class BollingerBands:
    def __init__(self, close, window, window_dev):
        self.close = close
        self.window = window
        self.window_dev = window_dev

    def calculate(self):
        try:
            mean = self.close.rolling(window=self.window, min_periods=1).mean()
            std = self.close.rolling(window=self.window, min_periods=1).std()
            upper = mean + self.window_dev * std
            lower = mean - self.window_dev * std
            return upper.fillna(0), lower.fillna(0)
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return pd.Series(np.nan), pd.Series(np.nan)


class MACD:
    def __init__(self, close, window_slow, window_fast, window_sign):
        self.close = close
        self.window_slow = window_slow
        self.window_fast = window_fast
        self.window_sign = window_sign

    def calculate(self):
        try:
            ema_fast = self.close.ewm(span=self.window_fast, adjust=False).mean()
            ema_slow = self.close.ewm(span=self.window_slow, adjust=False).mean()
            macd_line = ema_fast - ema_slow
            macd_signal = macd_line.ewm(span=self.window_sign, adjust=False).mean()
            return macd_line.fillna(0), macd_signal.fillna(0)
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return pd.Series(np.nan), pd.Series(np.nan)


class AverageTrueRange:
    def __init__(self, high, low, close, window):
        self.high = high
        self.low = low
        self.close = close
        self.window = window

    def calculate(self):
        try:
            high_low = self.high - self.low
            high_close = (self.high - self.close.shift()).abs()
            low_close = (self.low - self.close.shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            return tr.rolling(window=self.window, min_periods=1).mean().fillna(0)
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return pd.Series(np.nan)


class VWAP:
    def __init__(self, df):
        self.df = df

    def calculate(self):
        try:
            tp = (self.df['high'] + self.df['low'] + self.df['close']) / 3
            cumulative_tpv = (tp * self.df['volume']).cumsum()
            cumulative_volume = self.df['volume'].cumsum()
            return (cumulative_tpv / cumulative_volume).fillna(0)
        except Exception as e:
            logger.error(f"Error calculating VWAP: {e}")
            return pd.Series(np.nan, index=self.df.index)


class TechnicalIndicator:
    def __init__(self, params):
        self.params = params

    def calculate_all(self, df, category):
        logger.info(f"Calculating indicators for category: {category}")

        # 数据清理
        required_columns = ['close', 'high', 'low', 'volume']
        for col in required_columns:
            if col not in df.columns:
                logger.warning(f"Missing '{col}' column. Filling with default values (0).")
                df[col] = 0.0

        df = df.dropna(subset=['close', 'high', 'low'])  # 清理NaN

        used_pandas_ta = False
        if ta is not None:
            try:
                logger.info("Calculating indicators with pandas_ta...")
                # RSI（默认 pandas_ta 使用 RMA；为兼容 legacy SMA，可设置 talib=False + mamode='sma'）
                rsi_series = ta.rsi(close=df['close'], length=int(self.params['rsi_window']), talib=False, mamode='sma')
                df['rsi'] = rsi_series.fillna(0).astype(float)

                # Bollinger Bands
                bb = ta.bbands(close=df['close'], length=int(self.params['bollinger_window']), std=float(self.params['bollinger_dev']))
                if bb is not None and not bb.empty:
                    # BBL: lower, BBU: upper
                    lower_col = [c for c in bb.columns if c.startswith('BBL_')]
                    upper_col = [c for c in bb.columns if c.startswith('BBU_')]
                    df['bollinger_lower'] = bb[lower_col[0]].fillna(0).astype(float) if lower_col else 0.0
                    df['bollinger_upper'] = bb[upper_col[0]].fillna(0).astype(float) if upper_col else 0.0
                else:
                    df['bollinger_lower'] = 0.0
                    df['bollinger_upper'] = 0.0

                # MACD
                macd = ta.macd(close=df['close'], fast=int(self.params['macd_fast']), slow=int(self.params['macd_slow']), signal=int(self.params['macd_signal']))
                if macd is not None and not macd.empty:
                    macd_line_col = [c for c in macd.columns if c.startswith('MACD_') and not c.startswith('MACDh_') and not c.startswith('MACDs_')]
                    macd_signal_col = [c for c in macd.columns if c.startswith('MACDs_')]
                    df['macd'] = macd[macd_line_col[0]].fillna(0).astype(float) if macd_line_col else 0.0
                    df['macd_signal'] = macd[macd_signal_col[0]].fillna(0).astype(float) if macd_signal_col else 0.0
                else:
                    df['macd'] = 0.0
                    df['macd_signal'] = 0.0

                # ATR（与 legacy 接近：rolling mean，而非 RMA；pandas_ta 支持 mamode）
                atr_series = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=int(self.params['atr_window']), mamode='sma')
                df['atr'] = atr_series.fillna(0).astype(float)

                # VWAP（需要有效的 volume）
                if 'volume' in df.columns and float(df['volume'].sum()) > 0:
                    vwap_series = ta.vwap(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'])
                    df['vwap'] = vwap_series.fillna(0).astype(float)
                else:
                    logger.warning("VWAP skipped due to missing or invalid 'volume' data.")
                    df['vwap'] = 0.0

                used_pandas_ta = True
            except Exception as e:
                logger.error(f"pandas_ta calculation failed, falling back to legacy implementations: {e}", exc_info=True)

        if not used_pandas_ta:
            # 计算 RSI（legacy）
            logger.info("Calculating RSI (legacy)...")
            df['rsi'] = RSIIndicator(df['close'], self.params['rsi_window']).rsi()

            # 计算布林带（legacy）
            logger.info("Calculating Bollinger Bands (legacy)...")
            bb_upper, bb_lower = BollingerBands(
                df['close'], self.params['bollinger_window'], self.params['bollinger_dev']
            ).calculate()
            df['bollinger_upper'] = bb_upper
            df['bollinger_lower'] = bb_lower

            # 计算 MACD（legacy）
            logger.info("Calculating MACD (legacy)...")
            macd_line, macd_signal = MACD(
                df['close'], self.params['macd_slow'], self.params['macd_fast'], self.params['macd_signal']
            ).calculate()
            df['macd'] = macd_line
            df['macd_signal'] = macd_signal

            # 计算 ATR（legacy）
            logger.info("Calculating ATR (legacy)...")
            df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], self.params['atr_window']).calculate()

            # 计算 VWAP（legacy）
            logger.info("Calculating VWAP (legacy)...")
            if 'volume' in df.columns and df['volume'].sum() > 0:
                df['vwap'] = VWAP(df).calculate()
            else:
                logger.warning("VWAP skipped due to missing or invalid 'volume' data.")
                df['vwap'] = 0.0

        # 整合指标
        logger.info("Constructing indicators field...")
        df['indicators'] = df.apply(
            lambda row: {
                "rsi": row['rsi'],
                "bollinger_upper": row['bollinger_upper'],
                "bollinger_lower": row['bollinger_lower'],
                "macd": row['macd'],
                "macd_signal": row['macd_signal'],
                "atr": row['atr'],
                "vwap": row['vwap']
            }, axis=1
        )

        # 确保数值型字段不含 NaN
        numeric_columns = ['rsi', 'bollinger_upper', 'bollinger_lower', 'macd', 'macd_signal', 'atr', 'vwap']
        for col in numeric_columns:
            if col not in df.columns:
                df[col] = 0.0
        df[numeric_columns] = df[numeric_columns].fillna(0)

        logger.info("Indicators calculated successfully.")
        return df.reset_index(drop=True)
