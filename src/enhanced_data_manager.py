"""
增强的数据管理模块
Enhanced Data Manager

负责K线数据的获取、处理、存储和文件管理
修改为使用短文件名和覆盖模式
"""

import os
import pandas as pd
import json
import concurrent.futures
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
    
    def normalize_timeframe(self, timeframe):
        """将时间周期标准化为小写短格式（用于目录命名）"""
        return timeframe.lower()
    
    def get_okx_timeframe_format(self, timeframe):
        """将时间周期转换为OKX API接受的格式"""
        # 时间周期映射：配置文件格式 -> OKX API格式
        mapping = {
            '1m': '1m',    # 分钟级别保持不变
            '5m': '5m',
            '15m': '15m', 
            '30m': '30m',
            '1h': '1H',    # 小时级别需要大写
            '2h': '2H',
            '4h': '4H', 
            '6h': '6H',
            '12h': '12H',
            '1d': '1D',    # 天级别需要大写
            '3d': '3D',
            '1w': '1W'     # 周级别需要大写
        }
        return mapping.get(timeframe.lower(), timeframe)
    
    def _create_directory_structure(self):
        """创建数据存储目录结构"""
        try:
            base_path = Path(self.base_directory)
            base_path.mkdir(exist_ok=True)
            
            # 为每个时间周期创建目录（使用标准化名称）
            all_timeframes = []
            for category, tfs in self.config.get('timeframes', {}).items():
                all_timeframes.extend(tfs)
            
            for tf in all_timeframes:
                normalized_tf = self.normalize_timeframe(tf)
                tf_path = base_path / normalized_tf
                tf_path.mkdir(exist_ok=True)
            
            logger.info("Directory structure created successfully")
        except Exception as e:
            logger.error(f"Error creating directory structure: {e}")
    
    def _atomic_write(self, file_path, write_function):
        """原子性写入文件"""
        temp_path = str(file_path) + ".tmp"
        try:
            write_function(temp_path)
            os.replace(temp_path, file_path)
        except Exception as e:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
    
    def get_category_for_timeframe(self, timeframe):
        """获取时间周期对应的类别"""
        for category, tfs in self.config.get('timeframes', {}).items():
            if timeframe in tfs:
                return category
        return 'medium_term'  # 默认类别
    
    def fetch_and_process_kline_data(self, symbol=None, timeframes=None):
        """
        获取并处理K线数据 - 优化版本，支持并发处理和实时进度显示
        
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
        
        logger.info(f"🚀 开始获取 {symbol} 的 {len(timeframes)} 个时间周期数据...")
        
        # 使用线程池并发处理以提高效率
        max_workers = min(4, len(timeframes))  # 限制并发数以避免API限制
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_timeframe = {
                executor.submit(self._process_single_timeframe, symbol, tf): tf 
                for tf in timeframes
            }
            
            # 收集结果并显示进度
            completed = 0
            for future in concurrent.futures.as_completed(future_to_timeframe):
                timeframe = future_to_timeframe[future]
                completed += 1
                
                try:
                    result = future.result(timeout=60)  # 每个时间周期最多等待60秒
                    if result['success']:
                        results['success'].append(result['data'])
                        logger.info(f"[{completed}/{len(timeframes)}] {timeframe} processing completed ({result['data']['records_count']} records)")
                    else:
                        results['failed'].append({
                            'timeframe': timeframe,
                            'reason': result['error']
                        })
                        logger.warning(f"[{completed}/{len(timeframes)}] {timeframe} processing failed: {result['error']}")
                        
                except concurrent.futures.TimeoutError:
                    logger.error(f"[{completed}/{len(timeframes)}] {timeframe} processing timeout")
                    results['failed'].append({
                        'timeframe': timeframe,
                        'reason': 'Processing timeout (60s)'
                    })
                except Exception as e:
                    logger.error(f"[{completed}/{len(timeframes)}] {timeframe} processing exception: {e}")
                    results['failed'].append({
                        'timeframe': timeframe,
                        'reason': str(e)
                    })
        
        # 处理结果汇总
        processed_timeframes = [item['timeframe'] for item in results['success']]
        processed_normalized = [self.normalize_timeframe(tf) for tf in processed_timeframes]
        
        # 清理未获取的时间周期数据
        self.cleanup_unused_timeframes(processed_normalized)
        
        # 更新MCP清单
        self.update_mcp_manifest(processed_normalized)
        
        # 自动授权新生成的文件给MCP服务
        self._authorize_new_files(results)
        
        success_count = len(results['success'])
        failed_count = len(results['failed'])
        logger.info(f"Data fetching completed: success {success_count}, failed {failed_count}")
        
        return results
    
    def _process_single_timeframe(self, symbol, timeframe):
        """
        处理单个时间周期的数据获取（线程安全）
        
        Args:
            symbol (str): 交易对
            timeframe (str): 时间周期
        
        Returns:
            dict: 处理结果
        """
        try:
            # 获取配置
            kline_config = self.config.get('kline_config', {}).get(timeframe, {})
            fetch_count = kline_config.get('fetch_count', 100)
            output_count = kline_config.get('output_count', 50)
            
            # 获取K线数据
            kline_data = self._fetch_single_timeframe_data(
                symbol, timeframe, fetch_count, output_count
            )
            
            if kline_data.empty:
                return {
                    'success': False,
                    'error': 'No data received',
                    'timeframe': timeframe
                }
            
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
                symbol, timeframe
            )
            
            return {
                'success': True,
                'data': {
                    'timeframe': timeframe,
                    'records_count': len(kline_data_with_indicators),
                    'file_paths': save_result,
                    'category': category
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timeframe': timeframe
            }
    
    def _authorize_new_files(self, fetch_results):
        """自动授权新文件给MCP服务"""
        try:
            from src.mcp_service import load_manifest, save_manifest
            
            manifest = load_manifest()
            current_files = set(manifest.get('files', []))
            new_files = []
            
            # 收集所有新生成的文件路径
            for success_item in fetch_results.get('success', []):
                file_paths = success_item.get('file_paths', {})
                for file_type, file_path in file_paths.items():
                    if file_path:
                        # 转换为相对路径
                        try:
                            relative_path = str(Path(file_path).relative_to(Path("kline_data")))
                            if relative_path not in current_files:
                                new_files.append(relative_path)
                                current_files.add(relative_path)
                        except ValueError:
                            # 如果无法转换为相对路径，跳过
                            continue
            
            if new_files:
                manifest['files'] = sorted(list(current_files))
                save_manifest(manifest)
                logger.info(f"Auto-authorized {len(new_files)} new files for MCP access")
            
        except Exception as e:
            logger.warning(f"Failed to auto-authorize files: {e}")
    
    def _fetch_single_timeframe_data(self, symbol, timeframe, fetch_count, output_count):
        """
        获取单个时间周期的K线数据
        """
        try:
            # 将时间周期转换为OKX API格式
            okx_timeframe = self.get_okx_timeframe_format(timeframe)
            logger.info(f"Using OKX timeframe format: {timeframe} -> {okx_timeframe}")
            
            # 获取历史K线数据
            kline_df = self.data_fetcher.fetch_kline_data(
                instrument_id=symbol,
                bar=okx_timeframe,
                is_mark_price=False,
                limit=fetch_count
            )
            
            if kline_df.empty:
                return pd.DataFrame()
            
            # 获取当前未完结K线（使用OKX格式）
            try:
                current_kline_df = self.data_fetcher.get_current_kline(symbol, okx_timeframe)
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
    
    def _save_data(self, kline_data, indicator_data, symbol, timeframe):
        """
        保存K线数据和指标数据到文件（使用短文件名）
        
        Args:
            kline_data (pd.DataFrame): 原始K线数据
            indicator_data (pd.DataFrame): 包含指标的数据
            symbol (str): 交易对
            timeframe (str): 时间周期
        
        Returns:
            dict: 保存的文件路径信息
        """
        try:
            normalized_tf = self.normalize_timeframe(timeframe)
            base_path = Path(self.base_directory) / normalized_tf
            base_path.mkdir(exist_ok=True)
            
            file_paths = {}
            
            # 简单文件名：直接使用时间周期名称
            combined_path = base_path / f"{normalized_tf}.csv"
            
            # 原子性保存合并数据（K线+指标）
            def write_combined(temp_path):
                indicator_data.to_csv(temp_path, index=False)
            
            self._atomic_write(combined_path, write_combined)
            file_paths['combined'] = f"{normalized_tf}/{normalized_tf}.csv"
            
            # 保存元数据
            metadata = {
                'symbol': symbol,
                'timeframe': timeframe,
                'normalized_timeframe': normalized_tf,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'record_count': len(indicator_data),
                'columns': list(indicator_data.columns),
                'file_paths': file_paths
            }
            
            metadata_path = base_path / "metadata.json"
            def write_metadata(temp_path):
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            self._atomic_write(metadata_path, write_metadata)
            file_paths['metadata'] = f"{normalized_tf}/metadata.json"
            
            logger.info(f"Saved {timeframe} data to {combined_path}")
            return file_paths
            
        except Exception as e:
            logger.error(f"Error saving data for {timeframe}: {e}")
            return {}
    
    def cleanup_unused_timeframes(self, processed_timeframes):
        """
        清理本次未获取的时间周期数据
        
        Args:
            processed_timeframes (list): 本次处理的时间周期列表（已标准化）
        """
        try:
            base_path = Path(self.base_directory)
            if not base_path.exists():
                return
            
            deleted_files = []
            
            # 遍历所有时间周期目录
            for tf_dir in base_path.iterdir():
                if tf_dir.is_dir() and tf_dir.name not in ['logs', 'backup']:
                    tf_name = tf_dir.name
                    
                    # 如果这个时间周期本次没有处理，删除其文件
                    if tf_name not in processed_timeframes:
                        for file_pattern in [f"{tf_name}.csv", "metadata.json"]:
                            file_path = tf_dir / file_pattern
                            if file_path.exists():
                                file_path.unlink()
                                deleted_files.append(str(file_path))
                        
                        # 如果目录为空，删除目录
                        if not any(tf_dir.iterdir()):
                            tf_dir.rmdir()
                            deleted_files.append(str(tf_dir))
            
            if deleted_files:
                logger.info(f"Cleaned up {len(deleted_files)} unused timeframe files/directories")
            
        except Exception as e:
            logger.error(f"Error cleaning up unused timeframes: {e}")
    
    def update_mcp_manifest(self, processed_timeframes):
        """
        更新MCP清单文件
        
        Args:
            processed_timeframes (list): 处理的时间周期列表（已标准化）
        """
        try:
            manifest_path = Path(self.base_directory) / "manifest.json"
            
            # 构建新的文件列表
            files = []
            for tf in processed_timeframes:
                files.append(f"{tf}/{tf}.csv")
            
            manifest = {
                "files": sorted(files),
                "last_updated": datetime.utcnow().isoformat() + 'Z'
            }
            
            # 原子性保存manifest
            def write_manifest(temp_path):
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)
            
            self._atomic_write(manifest_path, write_manifest)
            logger.info(f"Updated MCP manifest with {len(files)} files")
            
        except Exception as e:
            logger.error(f"Error updating MCP manifest: {e}")
    
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
        清理旧文件（保留功能以兼容现有调用）
        """
        try:
            import time
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            base_path = Path(self.base_directory)
            deleted_files = []
            
            # 只清理备份目录或日志文件
            for pattern in ['backup/**/*', 'logs/**/*', '*.log']:
                for file_path in base_path.glob(pattern):
                    if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                        file_path.unlink()
                        deleted_files.append(str(file_path))
            
            logger.info(f"Cleaned up {len(deleted_files)} old files")
            return deleted_files
            
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
            return []