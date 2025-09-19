#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据获取器
Data Fetcher

提供OKX市场数据获取功能
"""

import os
import json
import time
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from src.logger import setup_logger

logger = setup_logger()

class DataFetcher:
    """数据获取器"""
    
    def __init__(self, api_key=None, api_secret=None, api_passphrase=None):
        """初始化数据获取器
        
        Args:
            api_key: OKX API Key
            api_secret: OKX API Secret
            api_passphrase: OKX API Passphrase
        """
        self.api_key = api_key or os.getenv('OKX_API_KEY')
        self.api_secret = api_secret or os.getenv('OKX_API_SECRET')
        self.api_passphrase = api_passphrase or os.getenv('OKX_API_PASSPHRASE')
        
        if not all([self.api_key, self.api_secret, self.api_passphrase]):
            logger.warning("OKX API credentials not fully configured")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("Data fetcher initialized successfully")
    
    def get_kline_data(self, symbol: str = 'BTC-USD-SWAP', timeframe: str = '1h', limit: int = 100) -> Dict[str, Any]:
        """获取K线数据"""
        try:
            if not self.enabled:
                return {
                    'success': False,
                    'error': 'API credentials not configured',
                    'data': None
                }
            
            # 模拟K线数据（实际应用中需要调用OKX API）
            base_price = 45000.0
            kline_data = []
            
            for i in range(limit):
                timestamp = datetime.utcnow() - timedelta(hours=i)
                price_variation = (i % 10 - 5) * 100  # 简单的价格变化模拟
                open_price = base_price + price_variation
                close_price = open_price + (i % 3 - 1) * 50
                high_price = max(open_price, close_price) + abs(i % 5) * 20
                low_price = min(open_price, close_price) - abs(i % 4) * 15
                volume = 1000 + (i % 20) * 100
                
                kline_data.append({
                    'timestamp': timestamp.isoformat(),
                    'open': round(open_price, 2),
                    'high': round(high_price, 2),
                    'low': round(low_price, 2),
                    'close': round(close_price, 2),
                    'volume': volume
                })
            
            logger.info(f"Retrieved {len(kline_data)} kline records for {symbol} {timeframe}")
            return {
                'success': True,
                'data': kline_data,
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get kline data: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_ticker_data(self, symbol: str = 'BTC-USD-SWAP') -> Dict[str, Any]:
        """获取行情数据"""
        try:
            if not self.enabled:
                return {
                    'success': False,
                    'error': 'API credentials not configured',
                    'data': None
                }
            
            # 模拟行情数据
            ticker_data = {
                'symbol': symbol,
                'last_price': '45123.45',
                'bid_price': '45120.00',
                'ask_price': '45125.00',
                'high_24h': '46000.00',
                'low_24h': '44000.00',
                'volume_24h': '12345.67',
                'change_24h': '2.34',
                'change_percent_24h': '5.45',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Retrieved ticker data for {symbol}")
            return {
                'success': True,
                'data': ticker_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get ticker data: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_market_summary(self) -> Dict[str, Any]:
        """获取市场摘要"""
        try:
            # 获取主要交易对的行情数据
            symbols = ['BTC-USD-SWAP', 'ETH-USD-SWAP', 'SOL-USD-SWAP']
            market_data = {}
            
            for symbol in symbols:
                ticker_result = self.get_ticker_data(symbol)
                if ticker_result.get('success'):
                    market_data[symbol] = ticker_result.get('data')
            
            summary = {
                'market_data': market_data,
                'total_symbols': len(market_data),
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'active' if self.enabled else 'disabled'
            }
            
            logger.info(f"Market summary generated for {len(market_data)} symbols")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get market summary: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def save_kline_to_csv(self, kline_data: List[Dict], filepath: str) -> bool:
        """保存K线数据到CSV文件"""
        try:
            df = pd.DataFrame(kline_data)
            df.to_csv(filepath, index=False)
            logger.info(f"Kline data saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save kline data: {e}")
            return False
    
    def is_enabled(self) -> bool:
        """检查数据获取器是否启用"""
        return self.enabled
    
    def get_current_kline(self, symbol: str = 'BTC-USD-SWAP', timeframe: str = '1h') -> pd.DataFrame:
        """获取当前未完结K线数据"""
        try:
            if not self.enabled:
                logger.warning("API credentials not configured for current kline")
                return pd.DataFrame()
            
            # 模拟当前未完结K线数据
            current_time = datetime.utcnow()
            base_price = 45000.0
            price_variation = 50  # 当前K线的价格变化
            
            current_kline = {
                'timestamp': current_time.isoformat(),
                'open': round(base_price, 2),
                'high': round(base_price + price_variation, 2),
                'low': round(base_price - price_variation/2, 2),
                'close': round(base_price + price_variation/3, 2),
                'volume': 500  # 当前K线成交量
            }
            
            logger.debug(f"Retrieved current kline for {symbol} {timeframe}")
            return pd.DataFrame([current_kline])
            
        except Exception as e:
            logger.error(f"Failed to get current kline: {e}")
            return pd.DataFrame()
    
    def get_status(self) -> Dict[str, Any]:
        """获取数据获取器状态"""
        return {
            'enabled': self.enabled,
            'api_configured': bool(self.api_key and self.api_secret and self.api_passphrase),
            'timestamp': datetime.utcnow().isoformat()
        }

# 向后兼容性函数
def fetch_market_data(symbol: str = 'BTC-USD-SWAP', timeframe: str = '1h') -> Dict[str, Any]:
    """获取市场数据（向后兼容）"""
    fetcher = DataFetcher()
    return fetcher.get_kline_data(symbol, timeframe)

if __name__ == "__main__":
    # 测试数据获取器
    fetcher = DataFetcher()
    print("Data Fetcher Status:", fetcher.get_status())
    print("Market Summary:", json.dumps(fetcher.get_market_summary(), indent=2, ensure_ascii=False))