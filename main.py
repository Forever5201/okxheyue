"""
AI交易系统主入口
Main Entry Point for AI Trading System

集成数据获取、技术指标计算、MCP服务和AI分析
"""

import os
import json
import time
import asyncio
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
        # 加载环境变量
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
        
        # 系统状态
        self.is_running = False
        self.last_update = None
        
    def fetch_all_data(self):
        """获取所有时间周期的数据"""
        try:
            logger.info("Starting comprehensive data fetch...")
            
            # 获取账户信息
            account_summary = self.data_manager.get_account_summary()
            
            # 获取市场信息  
            market_summary = self.data_manager.get_market_summary()
            
            # 获取并处理所有时间周期的K线数据
            results = self.data_manager.fetch_and_process_kline_data()
            
            # 自动授权新生成的文件给MCP服务
            self._authorize_new_files(results)
            
            # 保存运行摘要
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
    
    def setup_scheduler(self):
        """设置定时任务"""
        try:
            # 每小时获取一次数据
            schedule.every().hour.do(self.fetch_all_data)
            
            # 每天清理一次旧文件
            schedule.every().day.at("02:00").do(self._cleanup_old_files)
            
            logger.info("Scheduler setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup scheduler: {e}")
    
    def _cleanup_old_files(self):
        """清理旧文件"""
        try:
            deleted_files = self.data_manager.cleanup_old_files(days_to_keep=7)
            logger.info(f"Cleanup completed: removed {len(deleted_files)} old files")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    def start_scheduler(self):
        """启动定时任务"""
        logger.info("Starting scheduler...")
        self.is_running = True
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
            except KeyboardInterrupt:
                logger.info("Scheduler stopped by user")
                self.is_running = False
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def run_once(self):
        """运行一次数据获取"""
        logger.info("Running single data fetch...")
        return self.fetch_all_data()

def run_mcp_service():
    """运行MCP服务"""
    import uvicorn
    logger.info("Starting MCP service on port 5000...")
    
    # 确保MCP API密钥已设置
    if not os.getenv('MCP_API_KEY'):
        logger.error("MCP_API_KEY not set!")
        return
    
    try:
        uvicorn.run(
            "main:mcp_app", 
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
        
        # 设置定时任务
        trading_system.setup_scheduler()
        
        # 启动MCP服务
        print("\n🚀 启动MCP服务 (端口 5000)...")
        print("📊 系统已就绪 - AI现在可以通过MCP访问数据")
        print("\n" + "=" * 60)
        print("系统正在运行...")
        print("按 Ctrl+C 停止")
        print("=" * 60)
        
        # 在后台运行定时任务
        with ThreadPoolExecutor(max_workers=2) as executor:
            # 启动定时任务
            scheduler_future = executor.submit(trading_system.start_scheduler)
            
            # 启动MCP服务（主线程）
            run_mcp_service()
        
    except KeyboardInterrupt:
        print("\n\n🛑 用户终止程序")
    except Exception as e:
        print(f"\n❌ 系统错误: {e}")
        logger.error(f"System error: {e}")
    finally:
        print("\n👋 AI交易系统已停止")

if __name__ == "__main__":
    main(), encoding='utf-8') as f:\n                json.dump(summary, f, indent=2, ensure_ascii=False)\n            \n            logger.info(f\"Run summary saved to: {summary_file}\")\n            \n        except Exception as e:\n            logger.error(f\"Failed to save run summary: {e}\")\n    \n    def setup_scheduler(self):\n        \"\"\"设置定时任务\"\"\"\n        try:\n            # 每小时获取一次数据\n            schedule.every().hour.do(self.fetch_all_data)\n            \n            # 每天清理一次旧文件\n            schedule.every().day.at(\"02:00\").do(self._cleanup_old_files)\n            \n            logger.info(\"Scheduler setup completed\")\n            \n        except Exception as e:\n            logger.error(f\"Failed to setup scheduler: {e}\")\n    \n    def _cleanup_old_files(self):\n        \"\"\"清理旧文件\"\"\"\n        try:\n            deleted_files = self.data_manager.cleanup_old_files(days_to_keep=7)\n            logger.info(f\"Cleanup completed: removed {len(deleted_files)} old files\")\n        except Exception as e:\n            logger.error(f\"Error during cleanup: {e}\")\n    \n    def start_scheduler(self):\n        \"\"\"启动定时任务\"\"\"\n        logger.info(\"Starting scheduler...\")\n        self.is_running = True\n        \n        while self.is_running:\n            try:\n                schedule.run_pending()\n                time.sleep(60)  # 每分钟检查一次\n            except KeyboardInterrupt:\n                logger.info(\"Scheduler stopped by user\")\n                self.is_running = False\n                break\n            except Exception as e:\n                logger.error(f\"Scheduler error: {e}\")\n                time.sleep(60)\n    \n    def run_once(self):\n        \"\"\"运行一次数据获取\"\"\"\n        logger.info(\"Running single data fetch...\")\n        return self.fetch_all_data()\n\ndef run_mcp_service():\n    \"\"\"运行MCP服务\"\"\"\n    import uvicorn\n    logger.info(\"Starting MCP service on port 5000...\")\n    \n    # 确保MCP API密钥已设置\n    if not os.getenv('MCP_API_KEY'):\n        logger.error(\"MCP_API_KEY not set!\")\n        return\n    \n    try:\n        uvicorn.run(\n            \"main:mcp_app\", \n            host=\"0.0.0.0\", \n            port=5000, \n            log_level=\"info\",\n            reload=False\n        )\n    except Exception as e:\n        logger.error(f\"MCP service error: {e}\")\n\ndef main():\n    \"\"\"主函数\"\"\"\n    print(\"=\" * 60)\n    print(\"AI Trading System Starting...\")\n    print(\"=\" * 60)\n    \n    try:\n        # 初始化系统\n        trading_system = AITradingSystem()\n        \n        # 立即运行一次数据获取\n        print(\"\\n🔄 执行初始数据获取...\")\n        initial_results = trading_system.run_once()\n        \n        # 显示结果摘要\n        successful_timeframes = len(initial_results.get('success', []))\n        failed_timeframes = len(initial_results.get('failed', []))\n        print(f\"✅ 成功处理 {successful_timeframes} 个时间周期\")\n        \n        if failed_timeframes > 0:\n            print(f\"❌ 失败 {failed_timeframes} 个时间周期\")\n            for failed in initial_results.get('failed', []):\n                print(f\"   - {failed.get('timeframe')}: {failed.get('reason')}\")\n        \n        # 设置定时任务\n        trading_system.setup_scheduler()\n        \n        # 启动MCP服务\n        print(\"\\n🚀 启动MCP服务 (端口 5000)...\")\n        print(\"📊 系统已就绪 - AI现在可以通过MCP访问数据\")\n        print(\"\\n\" + \"=\" * 60)\n        print(\"系统正在运行...\")\n        print(\"按 Ctrl+C 停止\")\n        print(\"=\" * 60)\n        \n        # 在后台运行定时任务\n        with ThreadPoolExecutor(max_workers=2) as executor:\n            # 启动定时任务\n            scheduler_future = executor.submit(trading_system.start_scheduler)\n            \n            # 启动MCP服务（主线程）\n            run_mcp_service()\n        \n    except KeyboardInterrupt:\n        print(\"\\n\\n🛑 用户终止程序\")\n    except Exception as e:\n        print(f\"\\n❌ 系统错误: {e}\")\n        logger.error(f\"System error: {e}\")\n    finally:\n        print(\"\\n👋 AI交易系统已停止\")\n\nif __name__ == \"__main__\":\n    main()"