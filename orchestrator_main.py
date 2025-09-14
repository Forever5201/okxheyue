"""
AI交易系统工作流编排器 - 项目经理模式主入口
AI Trading System Orchestrator Main Entry - Project Manager Pattern

严格按照设计文档1.md实现的核心编排器，负责：
1. 准备工作：加载"岗位说明书"和"授权清单"
2. 下达指令与主循环：与AI模型进行多轮交互
3. 响应请求与调用MCP工具：翻译抽象工具调用到本地实现

这是整个AI分析系统的"项目经理"，确保AI始终在预设规则框架内运行。
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加src到Python路径
sys.path.append(str(Path(__file__).parent / "src"))

from src.logger import setup_logger
from src.ai_orchestrator import AIOrchestrator
from dotenv import load_dotenv

logger = setup_logger()

class OrchestratorMain:
    """
    主编排器类 - 严格按照设计文档实现的"项目经理"
    
    职责：
    1. 管理整个分析任务的生命周期
    2. 加载并向AI提供行为准则（系统提示词）和能力清单（工具定义）
    3. 作为AI与本地系统（文件、数据库等）之间唯一的通信桥梁
    4. 调用AI模型API，并处理其返回的请求
    5. 执行AI请求的本地工具，并将结果反馈给AI
    """
    
    def __init__(self):
        """初始化主编排器"""
        # 加载环境变量
        load_dotenv()
        
        # 验证必要的环境变量
        self._verify_environment()
        
        # 初始化AI编排器
        self.orchestrator = AIOrchestrator()
        
        logger.info("Orchestrator Main initialized successfully")
    
    def _verify_environment(self):
        """验证必要的环境变量"""
        required_vars = [
            'DASHSCOPE_API_KEY',  # AI模型API密钥
            'MCP_API_KEY',        # MCP服务密钥
            'OKX_API_KEY',        # OKX API密钥
            'OKX_API_SECRET',     # OKX API密钥
            'OKX_API_PASSPHRASE'  # OKX API密钥
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def execute_analysis(self, analysis_request: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        执行分析请求 - 设计文档核心工作流程的入口点
        
        这个方法实现了设计文档中描述的三步工作流程：
        1. 第一步：准备工作 (Initialization)
        2. 第二步：下达指令与主循环 (LLM Invocation & Main Loop)
        3. 第三步：响应请求与调用MCP工具 (Tool Execution)
        
        Args:
            analysis_request: 分析请求描述
            context: 可选的上下文信息
            
        Returns:
            Dict: 包含分析结果和执行日志的字典
        """
        try:
            logger.info(f"Starting analysis request: {analysis_request}")
            start_time = time.time()
            
            # 执行分析（内部已实现三步工作流程）
            result = self.orchestrator.analyze_market(analysis_request, context)
            
            execution_time = time.time() - start_time
            result['execution_time_seconds'] = execution_time
            
            if result.get('success', False):
                logger.info(f"Analysis completed successfully in {execution_time:.2f} seconds")
            else:
                logger.error(f"Analysis failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Critical error in analysis execution: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis": None,
                "execution_log": [f"❌ 分析执行失败: {str(e)}"],
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "orchestrator_main_status": "active",
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            **self.orchestrator.get_analysis_status()
        }
    
    def run_interactive_mode(self):
        """运行交互模式 - 用于测试和调试"""
        print("=" * 60)
        print("AI交易系统工作流编排器 - 交互模式")
        print("严格按照设计文档1.md实现")
        print("=" * 60)
        print("输入 'quit' 退出，输入 'status' 查看系统状态")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n请输入分析请求: ").strip()
                
                if user_input.lower() in ['quit', 'exit', '退出']:
                    print("系统退出")
                    break
                elif user_input.lower() in ['status', '状态']:
                    status = self.get_system_status()
                    print(json.dumps(status, indent=2, ensure_ascii=False))
                    continue
                elif not user_input:
                    print("请输入有效的分析请求")
                    continue
                
                print(f"\n🔄 执行分析请求: {user_input}")
                print("-" * 40)
                
                # 执行分析
                result = self.execute_analysis(user_input)
                
                # 显示结果
                if result.get('success', False):
                    print(f"✅ 分析成功完成")
                    print(f"📊 分析结果:")
                    print(result.get('analysis', '未获取到分析结果'))
                    print(f"⏱️ 执行时间: {result.get('execution_time_seconds', 0):.2f} 秒")
                    print(f"🔄 AI对话轮数: {result.get('iterations', 0)}")
                else:
                    print(f"❌ 分析失败: {result.get('error', 'Unknown error')}")
                
                # 显示执行日志
                if result.get('execution_log'):
                    print(f"\n📝 执行日志:")
                    for log_entry in result['execution_log']:
                        print(f"  {log_entry}")
                
                print("-" * 40)
                
            except KeyboardInterrupt:
                print("\n用户中断，系统退出")
                break
            except Exception as e:
                print(f"❌ 错误: {e}")
    
    def run_single_analysis(self, request: str, context: Optional[Dict] = None, output_file: Optional[str] = None) -> bool:
        """
        运行单次分析并可选择保存结果到文件
        
        Args:
            request: 分析请求
            context: 上下文信息
            output_file: 输出文件路径（可选）
            
        Returns:
            bool: 分析是否成功
        """
        try:
            result = self.execute_analysis(request, context)
            
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                logger.info(f"Analysis result saved to: {output_file}")
            
            return result.get('success', False)
            
        except Exception as e:
            logger.error(f"Error in single analysis: {e}")
            return False

def main():
    """主函数 - 设计文档要求的核心入口点"""
    try:
        # 初始化主编排器
        orchestrator_main = OrchestratorMain()
        
        # 检查命令行参数
        if len(sys.argv) > 1:
            # 命令行模式
            if sys.argv[1] == '--status':
                # 状态查看模式
                status = orchestrator_main.get_system_status()
                print(json.dumps(status, indent=2, ensure_ascii=False))
            elif sys.argv[1] == '--analysis':
                # 单次分析模式
                if len(sys.argv) < 3:
                    print("错误: 请提供分析请求")
                    print("用法: python orchestrator_main.py --analysis '分析请求'")
                    sys.exit(1)
                
                analysis_request = sys.argv[2]
                output_file = sys.argv[3] if len(sys.argv) > 3 else None
                
                success = orchestrator_main.run_single_analysis(analysis_request, output_file=output_file)
                sys.exit(0 if success else 1)
            else:
                print("未知参数，进入交互模式")
                orchestrator_main.run_interactive_mode()
        else:
            # 交互模式
            orchestrator_main.run_interactive_mode()
    
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        print(f"❌ 系统错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()