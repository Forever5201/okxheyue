"""
AI交易系统工作流编排器 - 基于计划的模式主入口
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# 添加src到Python路径
sys.path.append(str(Path(__file__).parent / "src"))

from src.logger import setup_logger
from src.plan_based_orchestrator import PlanBasedAIOrchestrator
from dotenv import load_dotenv

logger = setup_logger()

class PlanBasedOrchestratorMain:
    """
    主编排器类 - 基于计划的模式
    """
    
    def __init__(self):
        """初始化主编排器"""
        load_dotenv()
        # self._verify_environment() # 暂时禁用环境验证
        self.orchestrator = PlanBasedAIOrchestrator()
        logger.info("Plan-Based Orchestrator Main initialized successfully")
    
    def _verify_environment(self):
        """验证必要的环境变量"""
        required_vars = [] # 移除 'DASHSCOPE_API_KEY'
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            error_msg = f"Missing required environment variables: {", ".join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    def execute_analysis(self, analysis_request: str, context: Optional[Dict] = None) -> Dict:
        """
        执行分析请求
        """
        try:
            logger.info(f"Starting plan-based analysis request: {analysis_request}")
            result = self.orchestrator.analyze_market(analysis_request, context)
            if result.get('success', False):
                logger.info("Plan-based analysis completed successfully")
            else:
                logger.error(f"Plan-based analysis failed: {result.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            logger.error(f"Critical error in plan-based analysis execution: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }

def main():
    """主函数"""
    try:
        orchestrator_main = PlanBasedOrchestratorMain()
        
        # 示例分析请求
        # analysis_request = "分析一下最近24小时BTC-USDT-SWAP的行情走势，并结合当前账户持仓情况，给出交易建议。"
        analysis_request = "帮我分析一下大盘走势"
        
        print(f"执行分析请求: {analysis_request}")
        
        result = orchestrator_main.execute_analysis(analysis_request)
        
        print("\n" + "="*20 + " 分析完成 " + "="*20)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("="*50 + "\n")

    except Exception as e:
        logger.error(f"Critical error in main: {e}", exc_info=True)
        print(f"系统错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()