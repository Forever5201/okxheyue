"""
AI交易系统主入口
Main Entry Point for AI Trading System
"""

import os
import json
import time
import schedule
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

from src.logger import setup_logger
from src.enhanced_data_manager import EnhancedDataManager
from src.mcp_service import app as mcp_app

logger = setup_logger()

class AITradingSystem:
    def __init__(self):
        """初始化AI交易系统"""
        load_dotenv()
        
        # 检查必要的环境变量
        required_vars = ['OKX_API_KEY', 'OKX_API_SECRET', 'OKX_API_PASSPHRASE', 'MCP_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # 初始化数据管理器
        try:
            self.data_manager = EnhancedDataManager()
            logger.info("AI Trading System initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize data manager: {e}")
            raise
        
        self.is_running = False
        self.last_update = None
        
    def fetch_all_data(self):
        """获取所有时间周期的数据"""
        try:
            logger.info("Starting comprehensive data fetch...")
            
            account_summary = self.data_manager.get_account_summary()
            market_summary = self.data_manager.get_market_summary()
            results = self.data_manager.fetch_and_process_kline_data()
            
            self._authorize_new_files(results)
            self._save_run_summary(results, account_summary, market_summary)
            
            self.last_update = datetime.utcnow()
            logger.info("Data fetch completed successfully")
            
            return results
            
        except Exception as e:
            logger.error(f"Error in fetch_all_data: {e}")
            return {'success': [], 'failed': [], 'error': str(e)}
    
    def _authorize_new_files(self, fetch_results):
        """自动授权新文件给MCP服务"""
        try:
            from src.mcp_service import load_manifest, save_manifest
            
            manifest = load_manifest()
            current_files = set(manifest.get('files', []))
            new_files = []
            
            for success_item in fetch_results.get('success', []):
                file_paths = success_item.get('file_paths', {})
                for file_type, file_path in file_paths.items():
                    if file_path:
                        try:
                            relative_path = str(Path(file_path).relative_to(Path("kline_data")))
                            if relative_path not in current_files:
                                new_files.append(relative_path)
                                current_files.add(relative_path)
                        except ValueError:
                            continue
            
            if new_files:
                manifest['files'] = sorted(list(current_files))
                save_manifest(manifest)
                logger.info(f"Auto-authorized {len(new_files)} new files for MCP access")
            
        except Exception as e:
            logger.warning(f"Failed to auto-authorize files: {e}")
    
    def _save_run_summary(self, fetch_results, account_summary, market_summary):
        """保存运行摘要"""
        try:
            summary = {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'fetch_results': fetch_results,
                'account_summary': account_summary,
                'market_summary': market_summary,
                'system_status': {
                    'is_running': self.is_running,
                    'last_update': self.last_update.isoformat() + 'Z' if self.last_update else None
                }
            }
            
            summary_dir = Path('system_logs')
            summary_dir.mkdir(exist_ok=True)
            
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            summary_file = summary_dir / f'run_summary_{timestamp_str}.json'
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Run summary saved to: {summary_file}")
            
        except Exception as e:
            logger.error(f"Failed to save run summary: {e}")
    
    def run_once(self):
        """运行一次数据获取"""
        logger.info("Running single data fetch...")
        return self.fetch_all_data()

def run_mcp_service():
    """运行MCP服务"""
    import uvicorn
    logger.info("Starting MCP service on port 5000...")
    
    if not os.getenv('MCP_API_KEY'):
        logger.error("MCP_API_KEY not set!")
        return
    
    try:
        uvicorn.run(
            "main_clean:mcp_app", 
            host="0.0.0.0", 
            port=5000, 
            log_level="info",
            reload=False
        )
    except Exception as e:
        logger.error(f"MCP service error: {e}")

def main():
    """主函数"""
    print("=" * 60)
    print("AI Trading System Starting...")
    print("=" * 60)
    
    try:
        # 初始化系统
        trading_system = AITradingSystem()
        
        # 立即运行一次数据获取
        print("\n🔄 执行初始数据获取...")
        initial_results = trading_system.run_once()
        
        # 显示结果摘要
        successful_timeframes = len(initial_results.get('success', []))
        failed_timeframes = len(initial_results.get('failed', []))
        print(f"✅ 成功处理 {successful_timeframes} 个时间周期")
        
        if failed_timeframes > 0:
            print(f"❌ 失败 {failed_timeframes} 个时间周期")
            for failed in initial_results.get('failed', []):
                print(f"   - {failed.get('timeframe')}: {failed.get('reason')}")
        
        # 启动MCP服务
        print("\n🚀 启动MCP服务 (端口 5000)...")
        print("📊 系统已就绪 - AI现在可以通过MCP访问数据")
        print("\n" + "=" * 60)
        print("系统正在运行...")
        print("=" * 60)
        
        run_mcp_service()
        
    except KeyboardInterrupt:
        print("\n\n🛑 用户终止程序")
    except Exception as e:
        print(f"\n❌ 系统错误: {e}")
        logger.error(f"System error: {e}")
    finally:
        print("\n👋 AI交易系统已停止")

if __name__ == "__main__":
    main()