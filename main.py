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

from typing import Dict, Any
from src.logger import setup_logger
from src.enhanced_data_manager import EnhancedDataManager
from src.mcp_service import app as mcp_app
from src.message_queue import MessageQueueManager
from src.analysis_agent import AnalysisAgent

logger = setup_logger()

class AITradingSystem:
    def __init__(self):
        """初始化AI交易系统"""
        # 加载环境变量
        load_dotenv()
        
        # 检查必要的环境变量
        required_vars = ['OKX_API_KEY', 'OKX_API_SECRET', 'OKX_API_PASSPHRASE', 'MCP_API_KEY', 'DASHSCOPE_API_KEY']
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
        
        # 初始化消息队列和代理系统
        self._init_agent_system()
        
        # 系统状态
        self.is_running = False
        self.last_update = None
    
    def _init_agent_system(self):
        """初始化代理系统"""
        try:
            # 获取配置
            config = self.data_manager.config
            
            # 检查代理系统是否启用
            agent_system_config = config.get('agent_system', {})
            if not agent_system_config.get('enabled', False):
                logger.info("Agent system is disabled in configuration")
                self.message_queue = None
                self.analysis_agent = None
                return
            
            # 初始化消息队列
            mq_config = config.get('message_queue', {})
            self.message_queue = MessageQueueManager(mq_config)
            logger.info("Message queue initialized")
            
            # 初始化分析代理
            analysis_enabled = config.get('ai_analysis', {}).get('analysis_agent', {}).get('enabled', False)
            if analysis_enabled:
                self.analysis_agent = AnalysisAgent(config, self.message_queue)
                logger.info("Analysis agent initialized")
            else:
                self.analysis_agent = None
                logger.info("Analysis agent is disabled")
                
        except Exception as e:
            logger.error(f"Failed to initialize agent system: {e}")
            self.message_queue = None
            self.analysis_agent = None
        
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
            
            # 触发分析请求（如果代理系统启用）
            self._trigger_analysis_if_enabled(results)
            
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
    
    def _trigger_analysis_if_enabled(self, data_results: Dict[str, Any]):
        """如果代理系统启用，触发分析请求"""
        if not hasattr(self, 'message_queue') or not self.message_queue or not hasattr(self, 'analysis_agent') or not self.analysis_agent:
            return
        
        try:
            # 构建分析触发数据
            trigger_data = {
                "trigger_type": "data_update",
                "timestamp": datetime.utcnow().isoformat(),
                "data_summary": {
                    "successful_timeframes": len(data_results.get('success', [])),
                    "failed_timeframes": len(data_results.get('failed', [])),
                    "timeframes": [tf.get('timeframe') for tf in data_results.get('success', [])]
                }
            }
            
            # 发布分析请求消息
            topics = self.data_manager.config.get('message_queue', {}).get('topics', {})
            analysis_topic = topics.get('analysis_request', 'analysis.request')
            
            message_id = self.message_queue.publish(
                topic=analysis_topic,
                payload=trigger_data,
                sender="ai_trading_system"
            )
            
            logger.info(f"Published analysis request {message_id} after data update")
            
        except Exception as e:
            logger.error(f"Failed to trigger analysis: {e}")
    
    def start_agent_system(self):
        """启动代理系统"""
        if not hasattr(self, 'message_queue') or not self.message_queue:
            logger.info("Agent system not initialized, skipping start")
            return
        
        try:
            # 启动消息队列
            self.message_queue.start()
            logger.info("Message queue started")
            
            # 启动分析代理
            if hasattr(self, 'analysis_agent') and self.analysis_agent:
                self.analysis_agent.start()
                logger.info("Analysis agent started")
            
            logger.info("Agent system started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start agent system: {e}")
    
    def stop_agent_system(self):
        """停止代理系统"""
        if not hasattr(self, 'message_queue') or not self.message_queue:
            return
        
        try:
            # 停止分析代理
            if hasattr(self, 'analysis_agent') and self.analysis_agent:
                self.analysis_agent.stop()
                logger.info("Analysis agent stopped")
            
            # 停止消息队列
            self.message_queue.stop()
            logger.info("Message queue stopped")
            
            logger.info("Agent system stopped successfully")
            
        except Exception as e:
            logger.error(f"Failed to stop agent system: {e}")
    
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
        
        # 设置定时任务
        trading_system.setup_scheduler()
        
        # 启动代理系统（在数据获取之前，避免消息丢失）
        print("\n🤖 启动AI代理系统...")
        trading_system.start_agent_system()
        
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
        print("按 Ctrl+C 停止")
        print("=" * 60)
        
        # 在后台运行定时任务
        with ThreadPoolExecutor(max_workers=3) as executor:
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
        # 停止代理系统
        try:
            trading_system.stop_agent_system()
        except:
            pass
        print("\n👋 AI交易系统已停止")

if __name__ == "__main__":
    main()
