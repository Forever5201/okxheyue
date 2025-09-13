# get_data.py

import os
import json
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv
from src.logger import setup_logger
from src.config_loader import ConfigLoader
from src.account_fetcher import AccountFetcher
from src.data_fetcher import DataFetcher
from src.technical_indicator import TechnicalIndicator

logger = setup_logger()

def select_indicator_params(config, timeframe):
    """
    根据timeframe选择对应的指标参数
    :param config: 配置信息
    :param timeframe: 时间周期
    :return: 对应的指标参数
    """
    for category, intervals in config.get('timeframes', {}).items():
        if timeframe in intervals:
            return config['indicators'].get(category, config['indicators']['midterm'])
    return config['indicators']['midterm']

def fetch_and_process_kline(data_fetcher, symbol, timeframe, config, is_mark_price=False):
    """
    获取和处理K线数据，包括获取历史K线和当前未完结K线
    """
    try:
        # 获取该时间周期的配置
        kline_config = config.get('kline_config', {}).get(timeframe, {})
        fetch_count = kline_config.get('fetch_count', 100)  # 默认获取100条
        output_count = kline_config.get('output_count', 50) # 默认输出50条
        
        logger.info(f"Fetching K-line data for {timeframe}...")
        
        # 获取历史K线数据
        kline_df = data_fetcher.fetch_kline_data(
            instrument_id=symbol,
            bar=timeframe,
            is_mark_price=is_mark_price,
            limit=fetch_count
        )
        
        if kline_df.empty:
            logger.warning(f"No K-line data for {timeframe}.")
            return pd.DataFrame()

        # 获取当前未完结K线
        current_kline_df = data_fetcher.get_current_kline(symbol, timeframe)
        
        # 如果有未完结K线，添加到数据集
        if not current_kline_df.empty:
            kline_df = pd.concat([kline_df, current_kline_df])

        # 确保按时间排序并重置索引
        kline_df = kline_df.sort_values('timestamp', ascending=False)
        kline_df = kline_df.head(fetch_count).sort_values('timestamp')
        kline_df = kline_df.reset_index(drop=True)

        # 选择指标参数并计算技术指标
        indicator_params = select_indicator_params(config, timeframe)
        
        if 'volume' not in kline_df.columns:
            kline_df['volume'] = 0

        logger.info(f"Calculating indicators for {timeframe}...")
        indicator_calculator = TechnicalIndicator(params=indicator_params)
        kline_df = indicator_calculator.calculate_all(kline_df, category=timeframe)

        # 只保留最近的指定数量的K线
        if len(kline_df) > output_count:
            kline_df = kline_df.tail(output_count)

        # 设置K线状态
        kline_df["is_closed"] = True
        if not current_kline_df.empty:
            kline_df.iloc[-1, kline_df.columns.get_loc("is_closed")] = False

        return kline_df

    except Exception as e:
        logger.error(f"Error processing K-line data for {timeframe}: {e}")
        return pd.DataFrame()

def main():
    logger.info("Starting the data fetching process...")
    
    # 加载配置
    try:
        config_loader = ConfigLoader("config/config.yaml")
        config = config_loader.load_config()
        logger.info("Configuration loaded.")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return

    # 加载环境变量
    load_dotenv()
    api_key = os.getenv("OKX_API_KEY")
    secret_key = os.getenv("OKX_API_SECRET")
    passphrase = os.getenv("OKX_API_PASSPHRASE")
    trading_mode = os.getenv("TRADING_MODE", "0")  # 添加交易模式配置，默认为实盘

    if not all([api_key, secret_key, passphrase]):
        logger.error("API credentials missing.")
        return

    # 初始化API客户端
    try:
        account_fetcher = AccountFetcher(
            api_key, 
            secret_key, 
            passphrase,
            flag=trading_mode  # 使用环境变量中的交易模式
        )
        data_fetcher = DataFetcher(api_key, secret_key, passphrase)
    except Exception as e:
        logger.error(f"Error initializing modules: {e}")
        return

    # 获取账户详细信息
    logger.info("Fetching account data...")
    account_info = {"balance": 0, "positions": []}
    try:
        acct_bal = account_fetcher.get_balance()
        account_info = {
            "balance": acct_bal.get("balance", 0),
            "available_balance": acct_bal.get("available_balance", 0),
            "margin_ratio": acct_bal.get("margin_ratio", 0),
            "margin_frozen": acct_bal.get("margin_frozen", 0),
            "total_equity": acct_bal.get("total_equity", 0),
            "unrealized_pnl": acct_bal.get("unrealized_pnl", 0),
            "positions": account_fetcher.get_detailed_positions()
        }
    except Exception as e:
        logger.error(f"Error fetching account data: {e}")

    # 获取所有需要处理的时间周期
    all_timeframes = []
    for category, tfs in config.get('timeframes', {}).items():
        all_timeframes.extend(tfs)

    symbol = os.getenv("TRADING_SYMBOL", "BTC-USD-SWAP")  # 从环境变量加载交易对

    # 处理K线数据
    timeframes_data = {}
    logger.info("Fetching actual price timeframes data...")
    for tf in all_timeframes:
        df = fetch_and_process_kline(data_fetcher, symbol, tf, config, is_mark_price=False)
        if not df.empty:
            timeframes_data[tf] = {
                "type": "actual_price",
                "indicators_params": select_indicator_params(config, tf),
                "data": df.to_dict(orient="records")
            }

    # 获取当前市场数据
    current_market_data = {}
    try:
        # 获取市场基础数据
        market_data = data_fetcher.fetch_ticker(symbol)
        # 获取资金费率数据
        funding_data = data_fetcher.fetch_funding_rate(symbol)
        
        current_market_data = {
            "last_price": market_data.get("last_price", 0),
            "best_bid": market_data.get("best_bid", 0),
            "best_ask": market_data.get("best_ask", 0),
            "24h_high": market_data.get("24h_high", 0),
            "24h_low": market_data.get("24h_low", 0),
            "24h_volume": market_data.get("24h_volume", 0),
            "24h_turnover": market_data.get("24h_turnover", 0),
            "open_interest": market_data.get("open_interest", 0),
            "funding_rate": funding_data.get("funding_rate", 0),
            "next_funding_time": funding_data.get("next_funding_time", ""),
            "estimated_rate": funding_data.get("estimated_rate", 0),
            "timestamp": market_data.get("timestamp", 0),
            "time_iso": market_data.get("time_iso", "")
        }
    except Exception as e:
        logger.error(f"Error fetching market data: {e}")

    # 整合输出数据
    output_data = {
        "account_info": account_info,
        "current_market_data": current_market_data,
        "timeframes": timeframes_data,
        "metadata": {
            "fetch_time": pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "symbol": symbol,
            "data_version": "1.0"
        }
    }

    # 保存结果到文件
    try:
        with open("data.json", "w") as f:
            json.dump(output_data, f, indent=4)
        logger.info("Results saved to data.json")
    except Exception as e:
        logger.error(f"Error saving results: {e}")

if __name__ == "__main__":
    main()