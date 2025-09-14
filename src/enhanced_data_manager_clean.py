"""
增强的数据管理模块
Enhanced Data Manager

负责K线数据的获取、处理、存储和文件管理
"""

import os
import pandas as pd
import json
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from src.logger import setup_logger
from src.config_loader import ConfigLoader
from src.account_fetcher import AccountFetcher
from src.data_fetcher import DataFetcher
from src.enhanced_technical_indicator import EnhancedTechnicalIndicator

logger = setup_logger()

class EnhancedDataManager:
    def __init__(self, config_path="config/enhanced_config.yaml"):
        """
        初始化增强数据管理器
        
        Args:
            config_path (str): 配置文件路径
        """
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()
        
        # 加载环境变量
        load_dotenv()
        
        # 获取API凭证
        self.api_key = os.getenv("OKX_API_KEY")
        self.secret_key = os.getenv("OKX_API_SECRET")
        self.passphrase = os.getenv("OKX_API_PASSPHRASE")
        self.trading_mode = os.getenv("TRADING_MODE", "1")
        self.trading_symbol = os.getenv("TRADING_SYMBOL", "BTC-USD-SWAP")
        
        if not all([self.api_key, self.secret_key, self.passphrase]):
            raise ValueError("API credentials missing. Please set OKX_API_KEY, OKX_API_SECRET, and OKX_API_PASSPHRASE")
        
        # 初始化API客户端
        self.account_fetcher = AccountFetcher(
            self.api_key, 
            self.secret_key, 
            self.passphrase,
            flag=self.trading_mode
        )
        self.data_fetcher = DataFetcher(self.api_key, self.secret_key, self.passphrase)
        
        # 初始化技术指标计算器
        self.indicator_calculator = EnhancedTechnicalIndicator(self.config.get('indicators', {}))
        
        # 创建数据存储目录结构
        self.base_directory = self.config.get('storage', {}).get('base_directory', 'kline_data')
        self._create_directory_structure()
        
        logger.info("Enhanced Data Manager initialized successfully")
    
    def _create_directory_structure(self):
        """创建数据存储目录结构"""
        try:
            base_path = Path(self.base_directory)
            base_path.mkdir(exist_ok=True)
            
            # 为每个时间周期创建目录
            all_timeframes = []
            for category, tfs in self.config.get('timeframes', {}).items():
                all_timeframes.extend(tfs)
            
            for tf in all_timeframes:
                tf_path = base_path / tf
                tf_path.mkdir(exist_ok=True)
                
                # 创建子目录
                (tf_path / "kline").mkdir(exist_ok=True)
                (tf_path / "indicators").mkdir(exist_ok=True)
                (tf_path / "combined").mkdir(exist_ok=True)
            
            # 创建备份目录
            backup_dir = self.config.get('storage', {}).get('backup_directory', 'kline_data_backup')
            Path(backup_dir).mkdir(exist_ok=True)
            
            logger.info("Directory structure created successfully")
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
    
    def get_category_for_timeframe(self, timeframe):
        """获取时间周期对应的类别"""
        for category, tfs in self.config.get('timeframes', {}).items():
            if timeframe in tfs:
                return category
        return 'medium_term'  # 默认类别
    
    def fetch_and_process_kline_data(self, symbol=None, timeframes=None):
        """
        获取并处理K线数据
        
        Args:
            symbol (str): 交易对，默认使用配置中的
            timeframes (list): 时间周期列表，默认使用配置中的所有
        
        Returns:
            dict: 处理结果
        """
        if symbol is None:
            symbol = self.trading_symbol
        
        if timeframes is None:
            timeframes = []
            for category, tfs in self.config.get('timeframes', {}).items():
                timeframes.extend(tfs)
        
        results = {
            'success': [],
            'failed': [],
            'metadata': {
                'symbol': symbol,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'total_timeframes': len(timeframes)
            }
        }
        
        for timeframe in timeframes:
            try:
                logger.info(f"Processing {timeframe} data for {symbol}...")
                
                # 获取配置
                kline_config = self.config.get('kline_config', {}).get(timeframe, {})
                fetch_count = kline_config.get('fetch_count', 100)
                output_count = kline_config.get('output_count', 50)
                save_format = kline_config.get('save_format', 'parquet')
                
                # 获取K线数据
                kline_data = self._fetch_single_timeframe_data(
                    symbol, timeframe, fetch_count, output_count
                )
                
                if kline_data.empty:
                    logger.warning(f"No data received for {timeframe}")
                    results['failed'].append({
                        'timeframe': timeframe,
                        'reason': 'No data received'
                    })
                    continue
                
                # 计算技术指标
                category = self.get_category_for_timeframe(timeframe)
                kline_data_with_indicators = self.indicator_calculator.calculate_all_indicators(
                    kline_data.copy(), category
                )
                
                # 添加信号分析
                kline_data_with_indicators = self.indicator_calculator.add_signal_analysis(
                    kline_data_with_indicators
                )
                
                # 保存数据
                save_result = self._save_data(
                    kline_data, kline_data_with_indicators, 
                    symbol, timeframe, save_format
                )
                
                results['success'].append({
                    'timeframe': timeframe,
                    'records_count': len(kline_data_with_indicators),
                    'file_paths': save_result,
                    'category': category
                })
                
                logger.info(f"Successfully processed {timeframe}: {len(kline_data_with_indicators)} records")
                
            except Exception as e:
                logger.error(f"Error processing {timeframe}: {e}")
                results['failed'].append({
                    'timeframe': timeframe,
                    'reason': str(e)
                })
        
        return results
    
    def _fetch_single_timeframe_data(self, symbol, timeframe, fetch_count, output_count):
        """
        获取单个时间周期的K线数据
        """
        try:
            # 获取历史K线数据
            kline_df = self.data_fetcher.fetch_kline_data(
                instrument_id=symbol,
                bar=timeframe,
                is_mark_price=False,
                limit=fetch_count
            )
            
            if kline_df.empty:
                return pd.DataFrame()
            
            # 获取当前未完结K线
            try:
                current_kline_df = self.data_fetcher.get_current_kline(symbol, timeframe)
                if not current_kline_df.empty:
                    kline_df = pd.concat([kline_df, current_kline_df])
            except Exception as e:
                logger.warning(f"Could not get current kline for {timeframe}: {e}")
            
            # 数据清理和排序
            kline_df = kline_df.sort_values('timestamp', ascending=False)
            kline_df = kline_df.head(fetch_count).sort_values('timestamp')
            kline_df = kline_df.reset_index(drop=True)
            
            # 确保有成交量列
            if 'volume' not in kline_df.columns:
                kline_df['volume'] = 0
            
            # 只保留最近的指定数量
            if len(kline_df) > output_count:
                kline_df = kline_df.tail(output_count)
            
            # 设置K线状态
            kline_df["is_closed"] = True
            if len(kline_df) > 0:
                kline_df.iloc[-1, kline_df.columns.get_loc("is_closed")] = False
            
            return kline_df
            
        except Exception as e:
            logger.error(f"Error fetching {timeframe} data: {e}")
            return pd.DataFrame()
    
    def _save_data(self, kline_data, indicator_data, symbol, timeframe, format='parquet'):
        """
        保存K线数据和指标数据到文件
        """
        try:
            base_path = Path(self.base_directory) / timeframe
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            file_paths = {}
            
            # 保存原始K线数据
            kline_filename = f"{symbol}_{timeframe}_kline_{timestamp}.{format}"
            kline_path = base_path / "kline" / kline_filename
            
            if format == 'parquet':
                kline_data.to_parquet(kline_path, index=False)
            else:
                kline_data.to_csv(kline_path, index=False)
            
            file_paths['kline'] = str(kline_path)
            
            # 保存技术指标数据（仅指标列）
            indicator_columns = [col for col in indicator_data.columns 
                               if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'is_closed']]
            
            if indicator_columns:
                indicator_only_data = indicator_data[['timestamp'] + indicator_columns].copy()
                indicator_filename = f"{symbol}_{timeframe}_indicators_{timestamp}.{format}"
                indicator_path = base_path / "indicators" / indicator_filename
                
                if format == 'parquet':
                    indicator_only_data.to_parquet(indicator_path, index=False)
                else:
                    indicator_only_data.to_csv(indicator_path, index=False)
                
                file_paths['indicators'] = str(indicator_path)
            
            # 保存合并数据（K线+指标）
            combined_filename = f"{symbol}_{timeframe}_combined_{timestamp}.{format}"
            combined_path = base_path / "combined" / combined_filename
            
            if format == 'parquet':
                indicator_data.to_parquet(combined_path, index=False)
            else:
                indicator_data.to_csv(combined_path, index=False)
            
            file_paths['combined'] = str(combined_path)
            
            # 保存元数据
            metadata = {
                'symbol': symbol,
                'timeframe': timeframe,
                'timestamp': timestamp,
                'record_count': len(indicator_data),
                'columns': list(indicator_data.columns),
                'file_paths': file_paths,
                'format': format
            }
            
            metadata_filename = f"{symbol}_{timeframe}_metadata_{timestamp}.json"
            metadata_path = base_path / metadata_filename
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            file_paths['metadata'] = str(metadata_path)
            
            return file_paths
            
        except Exception as e:
            logger.error(f"Error saving data for {timeframe}: {e}")
            return {}
    
    def get_account_summary(self):
        """
        获取账户摘要信息
        """
        try:
            balance_info = self.account_fetcher.get_balance()
            positions_info = self.account_fetcher.get_detailed_positions()
            
            return {
                'balance': balance_info,
                'positions': positions_info,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return {
                'balance': {'balance': 0, 'available_balance': 0},
                'positions': [],
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'error': str(e)
            }
    
    def get_market_summary(self, symbol=None):
        """
        获取市场摘要信息
        """
        if symbol is None:
            symbol = self.trading_symbol
        
        try:
            # 获取市场数据
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
                'market_data': {},
                'funding_data': {},
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'error': str(e)
            }
    
    def cleanup_old_files(self, days_to_keep=7):
        """
        清理旧文件
        """
        try:
            import time
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            base_path = Path(self.base_directory)
            deleted_files = []
            
            for file_path in base_path.rglob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_files.append(str(file_path))
            
            logger.info(f"Cleaned up {len(deleted_files)} old files")
            return deleted_files
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            return []
