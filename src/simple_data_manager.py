"""
简化的数据管理模块
Simplified Data Manager for AI Trading System
"""

import os
import json
import pandas as pd
import requests
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
        
        # 初始化时授权所有现有文件
        self.authorize_all_existing_files_to_mcp()
    
    def _get_all_timeframes_from_config(self):
        """从配置文件获取所有时间周期"""
        timeframes_config = self.config.get('timeframes', {})
        all_timeframes = []
        
        for category, tfs in timeframes_config.items():
            if isinstance(tfs, list):
                all_timeframes.extend(tfs)
        
        # 如果配置为空，使用默认值
        if not all_timeframes:
            all_timeframes = ['1m', '5m', '15m', '30m', '1H', '2H', '4H', '6H', '12H', '1D']
            logger.warning("未找到配置的时间周期，使用默认值")
        
        return list(set(all_timeframes))  # 去重
    
    def _get_timeframes_by_category(self, category='medium_term'):
        """根据类别获取时间周期"""
        timeframes_config = self.config.get('timeframes', {})
        
        if category in timeframes_config:
            return timeframes_config[category]
        
        # 如果指定类别不存在，返回默认值
        logger.warning(f"未找到类别 '{category}' 的时间周期配置，使用默认值")
        return ['1H', '4H', '1D']
    
    def _get_indicator_config_by_category(self, category='medium_term'):
        """根据类别获取技术指标配置"""
        indicators_config = self.config.get('indicators', {})
        
        if category in indicators_config:
            return indicators_config[category]
        
        # 如果指定类别不存在，使用通用配置
        return indicators_config.get('common', {})
    
    def _auto_authorize_file_to_mcp(self, timeframe, filename):
        """自动授权新生成的文件到MCP服务"""
        try:
            # 构造文件相对路径（相对于kline_data目录）
            relative_path = f"{timeframe}/{filename}"
            
            # 获取MCP API Key
            mcp_api_key = os.getenv("MCP_API_KEY")
            if not mcp_api_key:
                logger.warning("未设置MCP_API_KEY，跳过自动授权")
                return
            
            # 调用MCP授权接口
            headers = {
                "x-api-key": mcp_api_key,
                "Content-Type": "application/json"
            }
            
            data = {
                "files": [relative_path]
            }
            
            # 使用配置中的MCP服务地址
            config = ConfigLoader('config/enhanced_config.yaml').load_config()
            mcp_config = config.get('mcp_service', {})
            host = mcp_config.get('host', '127.0.0.1')
            port = mcp_config.get('port', 5000)
            
            response = requests.post(
                f"http://{host}:{port}/authorize",
                json=data,
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"成功授权文件到MCP: {relative_path}")
            else:
                logger.warning(f"MCP授权失败: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"MCP服务不可用，跳过自动授权: {e}")
        except Exception as e:
            logger.error(f"自动授权文件失败: {e}")
    
    def _create_directories(self):
        """创建数据存储目录（配置驱动）"""
        try:
            base_path = Path(self.base_directory)
            base_path.mkdir(exist_ok=True)
            
            # 从配置文件获取所有时间周期
            timeframes = self._get_all_timeframes_from_config()
            
            for tf in timeframes:
                tf_path = base_path / tf
                tf_path.mkdir(exist_ok=True)
                # 不再创建子目录，直接在时间周期目录下存储文件
                
        except Exception as e:
            logger.error(f"Error creating directories: {e}")
    
    def fetch_and_process_data(self, symbol=None, timeframes=None, category='medium_term'):
        """获取并处理数据（配置驱动）"""
        if symbol is None:
            symbol = self.trading_symbol
        
        if timeframes is None:
            # 从配置文件获取指定类别的时间周期
            timeframes = self._get_timeframes_by_category(category)
        
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
                
                # 计算技术指标（使用配置驱动）
                kline_with_indicators = self.indicator_calculator.calculate_all_indicators(
                    kline_data.copy(), category
                )
                
                # 保存数据
                file_paths = self._save_timeframe_data(
                    kline_data, kline_with_indicators, symbol, timeframe
                )
                
                # 自动授权文件到MCP服务
                if 'filename' in file_paths:
                    self._auto_authorize_file_to_mcp(timeframe, file_paths['filename'])
                
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
        """保存单个时间周期的数据（单一文件存储）"""
        try:
            base_path = Path(self.base_directory) / timeframe
            
            # 使用固定文件名，便于MCP服务查找
            filename = f"{symbol}_{timeframe}_latest.csv"
            file_path = base_path / filename
            
            # 只保存包含K线+技术指标的完整数据
            indicator_data.to_csv(file_path, index=False)
            
            logger.info(f"Saved combined data to: {file_path}")
            
            return {
                'combined': str(file_path),
                'filename': filename  # 返回文件名供 MCP 服务使用
            }
            
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
    
    def authorize_all_existing_files_to_mcp(self):
        """授权所有现有数据文件到MCP服务（初始化时使用）"""
        try:
            base_path = Path(self.base_directory)
            if not base_path.exists():
                logger.info("数据目录不存在，跳过批量授权")
                return
            
            files_to_authorize = []
            
            # 扫描所有时间周期目录
            for timeframe_dir in base_path.iterdir():
                if timeframe_dir.is_dir():
                    # 查找 *_latest.csv 文件
                    for csv_file in timeframe_dir.glob("*_latest.csv"):
                        relative_path = f"{timeframe_dir.name}/{csv_file.name}"
                        files_to_authorize.append(relative_path)
            
            if not files_to_authorize:
                logger.info("未找到需要授权的数据文件")
                return
            
            # 批量授权
            mcp_api_key = os.getenv("MCP_API_KEY")
            if not mcp_api_key:
                logger.warning("未设置MCP_API_KEY，跳过批量授权")
                return
            
            headers = {
                "x-api-key": mcp_api_key,
                "Content-Type": "application/json"
            }
            
            data = {
                "files": files_to_authorize
            }
            
            # 使用配置中的MCP服务地址
            config = ConfigLoader('config/enhanced_config.yaml').load_config()
            mcp_config = config.get('mcp_service', {})
            host = mcp_config.get('host', '127.0.0.1')
            port = mcp_config.get('port', 5000)
            
            response = requests.post(
                f"http://{host}:{port}/authorize",
                json=data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"成功批量授权 {len(result.get('added', []))} 个文件到MCP")
            else:
                logger.warning(f"MCP批量授权失败: {response.status_code}")
                
        except Exception as e:
            logger.error(f"批量授权文件失败: {e}")
    
    def get_mcp_file_list(self):
        """获取MCP服务中的授权文件列表"""
        try:
            mcp_api_key = os.getenv("MCP_API_KEY")
            if not mcp_api_key:
                return {"error": "MCP_API_KEY not set"}
            
            headers = {"x-api-key": mcp_api_key}
            
            # 使用配置中的MCP服务地址
            config = ConfigLoader('config/enhanced_config.yaml').load_config()
            mcp_config = config.get('mcp_service', {})
            host = mcp_config.get('host', '127.0.0.1')
            port = mcp_config.get('port', 5000)
            
            response = requests.get(
                f"http://{host}:{port}/list_allowed_files",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"MCP service error: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Failed to connect to MCP service: {e}"}