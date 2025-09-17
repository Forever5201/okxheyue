"""
AI交易系统主入口 - 优化版本
Optimized Main Entry Point for AI Trading System

解决数据获取阻塞问题，提供实时进度反馈
"""

import os
import json
import time
import asyncio
import concurrent.futures
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

from typing import Dict, Any
from src.logger import setup_logger
from src.enhanced_data_manager import EnhancedDataManager
from src.mcp_service import app as mcp_app
from src.ai_orchestrator import AIOrchestrator

logger = setup_logger()

class OptimizedAITradingSystem:
    def __init__(self):
        """初始化优化版AI交易系统"""
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
            logger.info("✅ Optimized AI Trading System initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize data manager: {e}")
            raise
        
        # 初始化AI系统
        self._init_ai_system()
        
        # 系统状态
        self.is_running = False
        self.last_update = None
    
    def _init_ai_system(self):
        """初始化AI分析系统"""
        try:
            config = self.data_manager.config
            ai_analysis_config = config.get('ai_analysis', {})
            
            if not ai_analysis_config.get('enabled', True):
                logger.info("AI analysis system is disabled in configuration")
                self.ai_orchestrator = None
                return
            
            self.ai_orchestrator = AIOrchestrator()
            logger.info("✅ AI Orchestrator initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AI Orchestrator: {e}")
            self.ai_orchestrator = None
    
    def run_optimized_data_fetch(self):
        """运行优化的数据获取流程"""
        logger.info("🚀 启动优化数据获取流程...")
        
        try:
            # 显示配置信息
            timeframes_config = self.data_manager.config.get('timeframes', {})
            total_timeframes = sum(len(tfs) for tfs in timeframes_config.values())
            
            print(f"📊 系统配置:")
            print(f"   - 总时间周期: {total_timeframes}")
            for category, tfs in timeframes_config.items():
                print(f"   - {category}: {', '.join(tfs)}")
            print()
            
            # 并发获取数据
            logger.info("🔄 开始并发数据获取...")
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # 提交任务
                account_future = executor.submit(self._safe_get_account_summary)
                market_future = executor.submit(self._safe_get_market_summary)
                kline_future = executor.submit(self.data_manager.fetch_and_process_kline_data)
                
                # 等待K线数据（主要任务）
                print("⏳ 正在获取K线数据...")
                try:
                    results = kline_future.result(timeout=300)  # 5分钟超时
                    elapsed = time.time() - start_time
                    
                    success_count = len(results.get('success', []))
                    failed_count = len(results.get('failed', []))
                    
                    print(f"✅ K线数据获取完成! ({elapsed:.1f}秒)")
                    print(f"   - 成功: {success_count} 个时间周期")
                    if failed_count > 0:
                        print(f"   - 失败: {failed_count} 个时间周期")
                        for failed in results.get('failed', []):
                            print(f"     • {failed.get('timeframe')}: {failed.get('reason')}")
                    
                except concurrent.futures.TimeoutError:
                    logger.error("⏰ K线数据获取超时（5分钟）")
                    return {'success': [], 'failed': [], 'error': 'K-line data fetch timeout'}
                
                # 获取其他信息（非阻塞）
                try:
                    account_summary = account_future.result(timeout=30)
                    print("✅ 账户信息获取完成")
                except:
                    logger.warning("⚠️ 账户信息获取失败，使用默认值")
                    account_summary = {'error': 'Failed to fetch account info'}
                
                try:
                    market_summary = market_future.result(timeout=30)
                    print("✅ 市场信息获取完成")
                except:
                    logger.warning("⚠️ 市场信息获取失败，使用默认值")
                    market_summary = {'error': 'Failed to fetch market info'}
            
            # 保存运行摘要
            self._save_run_summary(results, account_summary, market_summary)
            
            # 触发AI分析（如果启用）
            if self.ai_orchestrator and success_count > 0:
                logger.info("🤖 触发AI分析...")
                self._trigger_analysis_if_enabled(results)
            
            self.last_update = datetime.now(timezone.utc)
            total_elapsed = time.time() - start_time
            
            print(f"\n🎉 数据获取流程完成!")
            print(f"   - 总耗时: {total_elapsed:.1f}秒")
            print(f"   - 成功率: {success_count}/{total_timeframes} ({success_count/total_timeframes*100:.1f}%)")
            
            return results
            
        except Exception as e:
            logger.error(f"💥 数据获取流程异常: {e}")
            return {'success': [], 'failed': [], 'error': str(e)}
    
    def _safe_get_account_summary(self):
        """安全获取账户摘要"""
        try:
            return self.data_manager.get_account_summary()
        except Exception as e:
            logger.warning(f"账户信息获取失败: {e}")
            return {'error': str(e)}
    
    def _safe_get_market_summary(self):
        """安全获取市场摘要"""
        try:
            return self.data_manager.get_market_summary()
        except Exception as e:
            logger.warning(f"市场信息获取失败: {e}")
            return {'error': str(e)}
    
    def _save_run_summary(self, fetch_results, account_summary, market_summary):
        """保存运行摘要"""
        try:
            summary = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'fetch_results': fetch_results,
                'account_summary': account_summary,
                'market_summary': market_summary,
                'system_status': {
                    'is_running': self.is_running,
                    'last_update': self.last_update.isoformat() if self.last_update else None
                }
            }
            
            summary_dir = Path('system_logs')
            summary_dir.mkdir(exist_ok=True)
            
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            summary_file = summary_dir / f'run_summary_{timestamp_str}.json'
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            
            logger.info(f"📝 运行摘要已保存: {summary_file}")
            
        except Exception as e:
            logger.error(f"保存运行摘要失败: {e}")
    
    def _trigger_analysis_if_enabled(self, data_results: Dict[str, Any]):
        """触发AI分析（如果启用）"""
        if not self.ai_orchestrator:
            logger.debug("AI Orchestrator not available, skipping analysis")
            return
        
        try:
            successful_timeframes = len(data_results.get('success', []))
            failed_timeframes = len(data_results.get('failed', []))
            timeframes = [tf.get('timeframe') for tf in data_results.get('success', [])]
            
            analysis_request = f"""请分析最新的市场数据。
            
数据更新摘要：
- 成功获取 {successful_timeframes} 个时间周期数据
- 失败 {failed_timeframes} 个时间周期
- 可用时间周期：{', '.join(timeframes)}
- 更新时间：{datetime.now(timezone.utc).isoformat()}

请基于最新数据进行市场分析，并提供交易建议。"""

            logger.info("🧠 开始AI市场分析...")
            analysis_result = self.ai_orchestrator.analyze_market(analysis_request)
            
            if analysis_result.get('success', False):
                logger.info("✅ AI分析完成")
                print("🧠 AI分析已完成，结果已保存到 system_logs/")
            else:
                logger.error(f"❌ AI分析失败: {analysis_result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"AI分析触发失败: {e}")
    
    def start_ai_analysis_system(self):
        """启动AI分析系统"""
        if not self.ai_orchestrator:
            logger.info("AI Orchestrator not initialized, skipping start")
            return
        
        try:
            status = self.ai_orchestrator.get_analysis_status()
            logger.info("🤖 AI Analysis System status verified")
            logger.info(f"Available tools: {status.get('available_tools', [])}")
            print("🤖 AI分析系统已就绪")
            
        except Exception as e:
            logger.error(f"Failed to start AI analysis system: {e}")

def run_mcp_service():
    """运行MCP服务"""
    import uvicorn
    logger.info("🚀 Starting MCP service on port 5000...")
    
    if not os.getenv('MCP_API_KEY'):
        logger.error("❌ MCP_API_KEY not set!")
        return
    
    try:
        uvicorn.run(
            "main_optimized:mcp_app", 
            host="0.0.0.0", 
            port=5000, 
            log_level="info",
            reload=False
        )
    except Exception as e:
        logger.error(f"MCP service error: {e}")

def main():
    """主函数 - 优化版本"""
    print("=" * 60)
    print("🚀 AI Trading System Starting (Optimized Version)")
    print("=" * 60)
    
    try:
        # 初始化系统
        trading_system = OptimizedAITradingSystem()
        
        # 启动AI分析系统
        print("\n🤖 启动AI分析系统...")
        trading_system.start_ai_analysis_system()
        
        # 执行优化的数据获取
        print("\n📊 执行优化数据获取...")
        initial_results = trading_system.run_optimized_data_fetch()
        
        # 启动MCP服务
        print(f"\n🚀 启动MCP服务 (端口 5000)...")
        print("📊 系统已就绪 - AI现在可以通过MCP访问数据")
        print("\n" + "=" * 60)
        print("✅ 系统启动完成!")
        print("🌐 MCP服务运行中... 按 Ctrl+C 停止")
        print("=" * 60)
        
        # 运行MCP服务（主线程）
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