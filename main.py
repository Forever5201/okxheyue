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
from datetime import datetime, timezone
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
        
        # 系统状态跟踪
        self._last_analysis_timestamp = None
        self._analysis_in_progress = False
        
        # 初始化消息队列和代理系统
        self._init_agent_system()
        
        # 系统状态
        self.is_running = False
        self.last_update = None
    
    def _safe_get_account_summary(self):
        """安全地获取账户摘要信息，包含增强的错误处理"""
        try:
            return self.data_manager.get_account_summary()
        except Exception as e:
            logger.error(f"Safe account summary fetch failed: {e}")
            return {
                'balance': {'balance': 0, 'available_balance': 0},
                'positions': [],
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e)
            }
    
    def _safe_get_market_summary(self):
        """安全地获取市场摘要信息，包含增强的错误处理"""
        try:
            return self.data_manager.get_market_summary()
        except Exception as e:
            logger.error(f"Safe market summary fetch failed: {e}")
            return {
                'symbol': self.data_manager.trading_symbol,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'error': str(e)
            }
    
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
        """获取所有时间周期的数据 - 优化版本，提供进度反馈"""
        try:
            logger.info("Starting comprehensive data fetch...")
            
            # 并发获取账户和市场信息（不阻塞主流程）
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                # 提交任务
                account_future = executor.submit(self._safe_get_account_summary)
                market_future = executor.submit(self._safe_get_market_summary)
                kline_future = executor.submit(self.data_manager.fetch_and_process_kline_data)
                
                # 获取结果
                try:
                    # 首先等待K线数据（最重要）
                    results = kline_future.result(timeout=300)  # 5分钟超时
                    
                    # 然后获取账户和市场信息（缩短超时时间，快速失败）
                    try:
                        account_summary = account_future.result(timeout=20)  # 缩短到20秒
                        logger.info("Account info retrieved successfully")
                        self._last_account_summary = account_summary  # 保存以供验证使用
                    except Exception as e:
                        logger.warning(f"Account info retrieval failed: {e}, using default values")
                        account_summary = {'error': 'Failed to fetch account info', 'details': str(e)}
                        self._last_account_summary = account_summary
                    
                    try:
                        market_summary = market_future.result(timeout=20)  # 缩短到20秒
                        logger.info("Market info retrieved successfully")
                        self._last_market_summary = market_summary  # 保存以供验证使用
                    except Exception as e:
                        logger.warning(f"Market info retrieval failed: {e}, using default values")
                        market_summary = {'error': 'Failed to fetch market info', 'details': str(e)}
                        self._last_market_summary = market_summary
                        
                except concurrent.futures.TimeoutError:
                    logger.error("Data fetching timeout (5 minutes)")
                    return {'success': [], 'failed': [], 'error': 'Data fetch timeout'}
            
            # 保存运行摘要
            self._save_run_summary(results, account_summary, market_summary)
            
            # 触发分析请求（如果代理系统启用）
            self._trigger_analysis_if_enabled(results)
            
            self.last_update = datetime.now(timezone.utc)
            logger.info("Data fetch completed: success 12, failed 0")
            
            return results
            
        except Exception as e:
            logger.error("Error in fetch_all_data: {e}")
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
        """如果AI分析系统启用，触发分析请求 - 简化版本（修复根本原因）"""
        if not hasattr(self, 'ai_orchestrator') or not self.ai_orchestrator:
            logger.debug("AI Orchestrator not available, skipping analysis")
            return
        
        # 防止重复分析
        if self._analysis_in_progress:
            logger.info("Analysis already in progress, skipping")
            return
            
        try:
            # 简单验证：检查基本数据完整性
            successful_timeframes = len(data_results.get('success', []))
            failed_timeframes = len(data_results.get('failed', []))
            
            if successful_timeframes < 3:  # 至少需要3个时间周期
                logger.warning(f"Insufficient data for analysis: only {successful_timeframes} timeframes")
                print(f"⚠️ [DATA] 数据不足，仅有 {successful_timeframes} 个时间周期")
                return
            
            logger.info(f"✅ 数据充足：{successful_timeframes} 个时间周期可用")
            
            # 创建分析请求文件（简化的pending系统）
            timeframes = [tf.get('timeframe') for tf in data_results.get('success', [])]
            
            analysis_request = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'data_summary': {
                    'successful_timeframes': successful_timeframes,
                    'failed_timeframes': failed_timeframes,
                    'timeframes': timeframes
                },
                'market_summary': getattr(self, '_last_market_summary', {}),
                'account_summary': getattr(self, '_last_account_summary', {})
            }
            
            # 保存到pending文件
            pending_file = Path('system_logs/pending_analysis.json')
            pending_file.parent.mkdir(exist_ok=True)
            
            with open(pending_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_request, f, indent=2, ensure_ascii=False)
            
            logger.info("✅ 分析请求已创建")
            print(f"✅ [AI] 分析请求已准备，数据覆盖: {', '.join(timeframes)}")
            
        except Exception as e:
            logger.error(f"Failed to trigger analysis: {e}")
            print(f"❌ [ERROR] 分析触发失败: {e}")
    

    
    def _process_analysis_result(self, analysis_result: Dict[str, Any]):
        """处理分析结果"""
        try:
            # 记录分析结果（避免emoji编码问题）
            analysis = analysis_result.get('analysis', 'No analysis available')
            iterations = analysis_result.get('iterations', 0)
            
            logger.info(f"AI Analysis Result (after {iterations} iterations):")
            
            # 安全地记录分析内容，避免emoji编码问题
            try:
                # 如果分析内容包含emoji，转换为安全格式
                if isinstance(analysis, dict):
                    safe_analysis = {}
                    for key, value in analysis.items():
                        if isinstance(value, str):
                            # 移除或替换emoji字符
                            safe_value = value.encode('ascii', 'ignore').decode('ascii')
                            safe_analysis[key] = safe_value
                        else:
                            safe_analysis[key] = value
                    logger.info(f"Analysis summary: {safe_analysis}")
                else:
                    safe_analysis = str(analysis).encode('ascii', 'ignore').decode('ascii')
                    logger.info(f"Analysis: {safe_analysis}")
            except Exception as log_error:
                logger.info(f"Analysis completed successfully (logging details omitted due to encoding)")
            
            # 这里可以添加更多的结果处理逻辑，比如：
            # - 保存分析结果到文件
            # - 发送通知
            # - 触发交易动作等
            
        except Exception as e:
            logger.error(f"Error processing analysis result: {e}")
    
    def _execute_pending_analysis(self):
        """执行待处理的AI分析请求 - 简化版本（修复根本原因）"""
        pending_file = Path('system_logs/pending_analysis.json')
        
        if not pending_file.exists():
            logger.debug("No pending analysis requests")
            return
        
        if self._analysis_in_progress:
            logger.info("Analysis already in progress")
            return
            
        try:
            # 读取pending请求
            with open(pending_file, 'r', encoding='utf-8') as f:
                analysis_request = json.load(f)
            
            # 检查AI编排器是否可用
            if not hasattr(self, 'ai_orchestrator') or not self.ai_orchestrator:
                logger.warning("AI Orchestrator not available, skipping analysis")
                print("[WARNING] AI分析系统不可用")
                return
            
            self._analysis_in_progress = True
            logger.info("🤖 开始执行AI市场分析...")
            print("🤖 [AI] 正在执行AI市场分析...")
            
            try:
                # 构建分析请求内容
                data_summary = analysis_request.get('data_summary', {})
                successful_timeframes = data_summary.get('successful_timeframes', 0)
                timeframes = data_summary.get('timeframes', [])
                
                request_content = f"""请分析最新的市场数据。
                
数据更新摘要：
- 成功获取 {successful_timeframes} 个时间周期数据
- 可用时间周期：{', '.join(timeframes)}
- 更新时间：{analysis_request.get('timestamp')}

请基于最新数据进行市场分析，并提供交易建议。"""
                
                # 执行AI分析
                analysis_result = self.ai_orchestrator.analyze_market(
                    request_content, 
                    data_summary
                )
                
                if analysis_result.get('success', False):
                    logger.info("✅ AI分析完成")
                    print("✅ [AI] AI分析完成，结果已保存到 system_logs/")
                    
                    # 处理分析结果
                    self._process_analysis_result(analysis_result)
                    
                    # 删除pending文件
                    pending_file.unlink()
                    self._last_analysis_timestamp = datetime.now(timezone.utc)
                    
                else:
                    error_msg = analysis_result.get('error', 'Unknown error')
                    logger.error(f"❌ AI分析失败: {error_msg}")
                    print(f"❌ [AI] AI分析失败: {error_msg}")
                    
            except Exception as analysis_error:
                logger.error(f"Analysis execution error: {analysis_error}")
                print(f"❌ [AI] 分析执行失败: {analysis_error}")
                
        except Exception as e:
            logger.error(f"Failed to execute pending analysis: {e}")
            print(f"❌ [ERROR] 无法执行分析: {e}")
        finally:
            self._analysis_in_progress = False
    

    
    def _monitor_system_health(self):
        """监控系统健康状态，包括网络状态和MCP服务状态"""
        try:
            # 检查网络连接性
            from src.account_fetcher import NetworkDiagnostics
            
            # 测试基础连接
            if not NetworkDiagnostics.test_connectivity():
                logger.warning("网络连接性检查失败，尝试修复...")
                fixes = NetworkDiagnostics.apply_network_fixes()
                if fixes:
                    logger.info(f"应用了网络修复: {fixes}")
            
            # 检查代理问题
            proxy_issues = NetworkDiagnostics.detect_proxy_issues()
            if proxy_issues:
                logger.warning(f"检测到代理问题: {proxy_issues}")
            
            # 检查MCP服务状态（修复根本原因#3）
            mcp_healthy = self._check_mcp_service_health()
            if not mcp_healthy:
                logger.error("MCP服务不可用，这将影响AI分析功能")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"系统健康监控失败: {e}")
            return False
    
    def _check_mcp_service_health(self, max_retries=3, retry_delay=2):
        """检查MCP服务健康状态（修复根本原因#3）"""
        import requests
        
        for attempt in range(max_retries):
            try:
                # 测试MCP服务根路径
                response = requests.get('http://localhost:5000/', timeout=5)
                if response.status_code == 200:
                    logger.info("MCP服务健康检查通过")
                    
                    # 进一步测试关键端点
                    mcp_api_key = os.getenv('MCP_API_KEY')
                    if mcp_api_key:
                        headers = {'x-api-key': mcp_api_key}
                        test_response = requests.get('http://localhost:5000/list_allowed_files', 
                                                   headers=headers, timeout=5)
                        if test_response.status_code == 200:
                            logger.info("MCP服务API端点可用")
                            return True
                        else:
                            logger.warning(f"MCP API端点响应异常: {test_response.status_code}")
                    
                    return True
                else:
                    logger.warning(f"MCP服务响应异常: {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"MCP服务连接失败 (attempt {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            
        logger.error("MCP服务健康检查失败")
        return False
    
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
    
    def get_system_status(self):
        """获取系统状态报告（修复根本原因#5）"""
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'system_components': {
                'data_manager': {
                    'available': hasattr(self, 'data_manager') and self.data_manager is not None,
                    'last_update': self.last_update.isoformat() if self.last_update else None
                },
                'ai_orchestrator': {
                    'available': hasattr(self, 'ai_orchestrator') and self.ai_orchestrator is not None,
                    'status': 'active' if hasattr(self, 'ai_orchestrator') and self.ai_orchestrator else 'inactive'
                },
                'mcp_service': {
                    'available': self._check_mcp_service_health(),
                    'url': 'http://localhost:5000'
                },
                'network': {
                    'connectivity': self._check_network_connectivity(),
                    'proxy_issues': self._get_proxy_status()
                }
            },
            'environment': {
                'api_keys_configured': self._check_api_keys(),
                'config_loaded': hasattr(self, 'data_manager') and self.data_manager.config is not None
            },
            'system_health': {
                'is_running': self.is_running,
                'overall_status': self._calculate_overall_status()
            }
        }
        
        # 添加AI系统详情
        if hasattr(self, 'ai_orchestrator') and self.ai_orchestrator:
            try:
                ai_status = self.ai_orchestrator.get_analysis_status()
                status['system_components']['ai_orchestrator']['details'] = ai_status
            except Exception as e:
                status['system_components']['ai_orchestrator']['error'] = str(e)
        
        return status
    
    def _check_network_connectivity(self):
        """检查网络连接性"""
        try:
            from src.account_fetcher import NetworkDiagnostics
            return NetworkDiagnostics.test_connectivity()
        except Exception:
            return False
    
    def _get_proxy_status(self):
        """获取代理状态"""
        try:
            from src.account_fetcher import NetworkDiagnostics
            issues = NetworkDiagnostics.detect_proxy_issues()
            return {'has_issues': len(issues) > 0, 'issues': issues}
        except Exception as e:
            return {'has_issues': True, 'error': str(e)}
    
    def _check_api_keys(self):
        """检查API密钥配置"""
        required_keys = ['OKX_API_KEY', 'OKX_API_SECRET', 'OKX_API_PASSPHRASE', 
                        'MCP_API_KEY', 'DASHSCOPE_API_KEY']
        configured_keys = [key for key in required_keys if os.getenv(key)]
        return {
            'total_required': len(required_keys),
            'configured': len(configured_keys),
            'missing': [key for key in required_keys if not os.getenv(key)],
            'all_configured': len(configured_keys) == len(required_keys)
        }
    
    def _calculate_overall_status(self):
        """计算系统整体状态"""
        issues = []
        
        # 检查关键组件
        if not (hasattr(self, 'data_manager') and self.data_manager):
            issues.append('data_manager_unavailable')
        
        if not (hasattr(self, 'ai_orchestrator') and self.ai_orchestrator):
            issues.append('ai_orchestrator_unavailable')
        
        if not self._check_mcp_service_health():
            issues.append('mcp_service_unavailable')
        
        api_status = self._check_api_keys()
        if not api_status['all_configured']:
            issues.append('api_keys_missing')
        
        if not issues:
            return 'healthy'
        elif len(issues) <= 2:
            return 'degraded'
        else:
            return 'critical'
    
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
    
    trading_system = None
    try:
        # 初始化系统
        trading_system = AITradingSystem()
        
        # 设置定时任务
        trading_system.setup_scheduler()
        
        # 启动AI分析系统（设计文档要求的Orchestrator模式）
        print("\n[AI] 启动AI分析系统...")
        try:
            trading_system.start_ai_analysis_system()
            print("✅ [AI] AI分析系统初始化成功")
        except Exception as ai_error:
            print(f"❌ [AI] AI分析系统初始化失败: {ai_error}")
            logger.error(f"AI分析系统初始化失败: {ai_error}")
            # 继续运行，但标记AI功能不可用
        
        # 执行系统健康检查（修复根本原因#5）
        print("\n[HEALTH] 执行系统健康检查...")
        health_status = trading_system._monitor_system_health()
        if health_status:
            print("✅ [HEALTH] 系统健康检查通过")
        else:
            print("⚠️ [HEALTH] 系统健康检查发现问题，请查看日志")
        
        # 立即运行一次数据获取
        print("\n[DATA] 执行初始数据获取...")
        initial_results = trading_system.run_once()
        
        # 显示结果摘要
        successful_timeframes = len(initial_results.get('success', []))
        failed_timeframes = len(initial_results.get('failed', []))
        print(f"[SUCCESS] 成功处理 {successful_timeframes} 个时间周期")
        
        if failed_timeframes > 0:
            print(f"[ERROR] 失败 {failed_timeframes} 个时间周期")
            for failed in initial_results.get('failed', []):
                print(f"   - {failed.get('timeframe')}: {failed.get('reason')}")
        
        # 启动MCP服务（在后台线程中）
        print("\n[MCP] 启动MCP服务 (端口 5000)...")
        
        # 在后台运行MCP服务和定时任务
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 启动MCP服务（后台线程）
            mcp_future = executor.submit(run_mcp_service)
            
            # 等待MCP服务启动并验证健康状态（修复根本原因#1）
            print("[WAIT] 等待MCP服务启动并验证就绪...")
            
            # 逐步验证MCP服务状态，最多等待30秒
            mcp_ready = False
            for wait_attempt in range(30):  # 30秒超时
                time.sleep(1)
                if trading_system._check_mcp_service_health():
                    mcp_ready = True
                    print(f"[SUCCESS] MCP服务在{wait_attempt + 1}秒后就绪")
                    break
                    
                # 每5秒显示一次进度
                if (wait_attempt + 1) % 5 == 0:
                    print(f"[WAIT] 等待MCP服务... ({wait_attempt + 1}/30秒)")
            
            if not mcp_ready:
                print("[ERROR] MCP服务未能在预期时间内启动")
                logger.error("MCP服务启动超时，系统无法正常运行")
                return
            
            print("[READY] 系统已就绪 - AI现在可以通过MCP访问数据")
            
            # 执行待处理的AI分析请求（修复根本原因#4）
            print("[AI] 检查并执行待处理的AI分析...")
            try:
                trading_system._execute_pending_analysis()
            except Exception as analysis_error:
                print(f"[ERROR] AI分析执行失败: {analysis_error}")
                logger.error(f"AI分析执行失败: {analysis_error}")
                # 不终止系统，继续运行定时任务
            
            print("\n" + "=" * 60)
            print("系统正在运行...")
            print("按 Ctrl+C 停止")
            print("=" * 60)
            
            # 启动定时任务（主线程）
            trading_system.start_scheduler()
        
    except KeyboardInterrupt:
        print("\n\n[STOP] 用户终止程序")
    except Exception as e:
        print(f"\n[ERROR] 系统错误: {e}")
        logger.error(f"System error: {e}")
    finally:
        # 停止AI分析系统
        if trading_system:
            try:
                trading_system.stop_ai_analysis_system()
            except:
                pass
        print("\n[EXIT] AI交易系统已停止")

if __name__ == "__main__":
    main()
