"""
简化的数据管理模块
Simplified Data Manager for AI Trading System
"""

import os
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from src.logger import setup_logger
from src.config_loader import ConfigLoader
from src.account_fetcher import AccountFetcher
from src.data_fetcher import DataFetcher
from src.enhanced_technical_indicator import EnhancedTechnicalIndicator

logger = setup_logger()

class SimpleDataManager:
    def __init__(self, config_path="config/enhanced_config.yaml"):
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()
        
        load_dotenv()
        
        self.api_key = os.getenv("OKX_API_KEY")
        self.secret_key = os.getenv("OKX_API_SECRET")
        self.passphrase = os.getenv("OKX_API_PASSPHRASE")
        self.trading_mode = os.getenv("TRADING_MODE", "1")
        self.trading_symbol = os.getenv("TRADING_SYMBOL", "BTC-USD-SWAP")
        
        if not all([self.api_key, self.secret_key, self.passphrase]):
            raise ValueError("API credentials missing")
        
        self.account_fetcher = AccountFetcher(
            self.api_key, self.secret_key, self.passphrase, flag=self.trading_mode
        )
        self.data_fetcher = DataFetcher(self.api_key, self.secret_key, self.passphrase)
        self.indicator_calculator = EnhancedTechnicalIndicator(self.config.get('indicators', {}))
        
        self.base_directory = 'kline_data'
        self._create_directories()
        
        logger.info("Simple Data Manager initialized successfully")
    
    def _create_directories(self):
        """创建数据存储目录"""
        try:
            base_path = Path(self.base_directory)
            base_path.mkdir(exist_ok=True)
            
            timeframes = ['1m', '5m', '15m', '30m', '1H', '2H', '4H', '6H', '12H', '1D']
            for tf in timeframes:
                tf_path = base_path / tf
                tf_path.mkdir(exist_ok=True)
                (tf_path / "kline").mkdir(exist_ok=True)
                (tf_path / "indicators").mkdir(exist_ok=True)
                (tf_path / "combined").mkdir(exist_ok=True)
                
        except Exception as e:
            logger.error(f"Error creating directories: {e}")
    
    def fetch_and_process_data(self, symbol=None, timeframes=None):
        """获取并处理数据"""
        if symbol is None:
            symbol = self.trading_symbol
        
        if timeframes is None:
            timeframes = ['1H', '4H', '1D']  # 默认时间周期
        
        results = {'success': [], 'failed': []}
        
        for timeframe in timeframes:
            try:
                logger.info(f"Processing {timeframe} for {symbol}")
                
                # 获取K线数据
                kline_data = self.data_fetcher.fetch_kline_data(
                    instrument_id=symbol, bar=timeframe, limit=100
                )
                
                if kline_data.empty:
                    results['failed'].append({
                        'timeframe': timeframe,
                        'reason': 'No data received'
                    })
                    continue
                
                # 计算技术指标
                kline_with_indicators = self.indicator_calculator.calculate_all_indicators(
                    kline_data.copy(), 'medium_term'
                )
                
                # 保存数据
                file_paths = self._save_timeframe_data(
                    kline_data, kline_with_indicators, symbol, timeframe
                )
                
                results['success'].append({
                    'timeframe': timeframe,
                    'records': len(kline_with_indicators),
                    'file_paths': file_paths
                })
                
                logger.info(f"Successfully processed {timeframe}: {len(kline_with_indicators)} records")
                
            except Exception as e:
                logger.error(f"Error processing {timeframe}: {e}")
                results['failed'].append({
                    'timeframe': timeframe,
                    'reason': str(e)
                })
        
        return results
    
    def _save_timeframe_data(self, kline_data, indicator_data, symbol, timeframe):
        """保存单个时间周期的数据"""
        try:
            base_path = Path(self.base_directory) / timeframe
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            file_paths = {}
            
            # 保存K线数据
            kline_file = base_path / "kline" / f"{symbol}_{timeframe}_kline_{timestamp}.csv"
            kline_data.to_csv(kline_file, index=False)
            file_paths['kline'] = str(kline_file)
            
            # 保存合并数据
            combined_file = base_path / "combined" / f"{symbol}_{timeframe}_combined_{timestamp}.csv"
            indicator_data.to_csv(combined_file, index=False)
            file_paths['combined'] = str(combined_file)
            
            return file_paths
            
        except Exception as e:
            logger.error(f"Error saving data for {timeframe}: {e}")
            return {}
    
    def get_account_summary(self):
        """获取账户信息"""
        try:
            balance = self.account_fetcher.get_balance()
            positions = self.account_fetcher.get_detailed_positions()
            return {
                'balance': balance,
                'positions': positions,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return {
                'balance': {'balance': 0},
                'positions': [],
                'error': str(e)
            }
    
    def get_market_summary(self, symbol=None):
        """获取市场信息"""
        if symbol is None:
            symbol = self.trading_symbol
            
        try:
            market_data = self.data_fetcher.fetch_ticker(symbol)
            funding_data = self.data_fetcher.fetch_funding_rate(symbol)
            return {
                'symbol': symbol,
                'market_data': market_data,
                'funding_data': funding_data,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        except Exception as e:
            logger.error(f"Error getting market summary: {e}")
            return {
                'symbol': symbol,
                'error': str(e)
            }