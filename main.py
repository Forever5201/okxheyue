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
from src.ai_orchestrator import AIOrchestrator

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
        """初始化AI分析系统 - 使用设计文档要求的Orchestrator模式"""
        try:
            # 获取配置
            config = self.data_manager.config
            
            # 检查AI分析系统是否启用
            ai_analysis_config = config.get('ai_analysis', {})
            if not ai_analysis_config.get('enabled', True):
                logger.info("AI analysis system is disabled in configuration")
                self.ai_orchestrator = None
                return
            
            # 初始化AI编排器（按照设计文档的项目经理模式）
            try:
                self.ai_orchestrator = AIOrchestrator()
                logger.info("AI Orchestrator initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize AI Orchestrator: {e}")
                self.ai_orchestrator = None
                
        except Exception as e:
            logger.error(f"Failed to initialize AI analysis system: {e}")
            self.ai_orchestrator = None
        
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
        """如果AI分析系统启用，触发分析请求"""
        if not hasattr(self, 'ai_orchestrator') or not self.ai_orchestrator:
            logger.debug("AI Orchestrator not available, skipping analysis")
            return
        
        try:
            # 构建分析请求
            successful_timeframes = len(data_results.get('success', []))
            failed_timeframes = len(data_results.get('failed', []))
            timeframes = [tf.get('timeframe') for tf in data_results.get('success', [])]
            
            analysis_request = f"""请分析最新的市场数据。
            
数据更新摘要：
- 成功获取 {successful_timeframes} 个时间周期数据
- 失败 {failed_timeframes} 个时间周期
- 可用时间周期：{', '.join(timeframes)}
- 更新时间：{datetime.utcnow().isoformat()}

请基于最新数据进行市场分析，并提供交易建议。"""

            # 使用AI编排器执行分析
            logger.info("Triggering AI analysis after data update")
            analysis_result = self.ai_orchestrator.analyze_market(analysis_request)
            
            if analysis_result.get('success', False):
                logger.info("AI analysis completed successfully")
                # 这里可以添加对分析结果的处理逻辑
                self._process_analysis_result(analysis_result)
            else:
                logger.error(f"AI analysis failed: {analysis_result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"Failed to trigger analysis: {e}")
    
    def _process_analysis_result(self, analysis_result: Dict[str, Any]):
        """处理分析结果"""
        try:
            # 记录分析结果
            analysis = analysis_result.get('analysis', 'No analysis available')
            iterations = analysis_result.get('iterations', 0)
            
            logger.info(f"AI Analysis Result (after {iterations} iterations):")
            logger.info(f"Analysis: {analysis}")
            
            # 这里可以添加更多的结果处理逻辑，比如：
            # - 保存分析结果到文件
            # - 发送通知
            # - 触发交易动作等
            
        except Exception as e:
            logger.error(f"Error processing analysis result: {e}")
    
    def start_ai_analysis_system(self):
        """启动AI分析系统"""
        if not hasattr(self, 'ai_orchestrator') or not self.ai_orchestrator:
            logger.info("AI Orchestrator not initialized, skipping start")
            return
        
        try:
            # AI编排器不需要显式启动，它是基于调用的模式
            # 验证系统状态
            status = self.ai_orchestrator.get_analysis_status()
            logger.info("AI Analysis System status verified")
            logger.info(f"Available tools: {status.get('available_tools', [])}")
            logger.info("AI Analysis System ready for use")
            
        except Exception as e:
            logger.error(f"Failed to start AI analysis system: {e}")
    
    def stop_ai_analysis_system(self):
        """停止AI分析系统"""
        try:
            # AI编排器不需要显式停止
            # 记录停止信息
            logger.info("AI Analysis System stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop AI analysis system: {e}")
    
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
        
        # 启动AI分析系统（设计文档要求的Orchestrator模式）
        print("\n🤖 启动AI分析系统...")
        trading_system.start_ai_analysis_system()
        
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
        # 停止AI分析系统
        try:
            trading_system.stop_ai_analysis_system()
        except:
            pass
        print("\n👋 AI交易系统已停止")

if __name__ == "__main__":
    main()
