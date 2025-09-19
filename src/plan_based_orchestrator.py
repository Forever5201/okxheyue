"""
AI交易系统编排器 - 项目经理模式 (基于计划的版本)
AI Trading System Orchestrator - Plan-Based Project Manager Pattern

此版本实现了更严格的“计划-执行”工作流，以满足更高级的自主代理需求。
- **阶段一：计划生成** - AI首先被要求创建一个详细的、结构化的分析计划。
- **阶段二：计划执行** - 编排器严格按照计划的每个步骤，指导AI完成执行和数据收集。
- **阶段三：综合报告** - AI最后根据所有步骤的结果，生成一份完整的最终报告。
"""

import json
import logging
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from src.logger import setup_logger
from src.config_loader import ConfigLoader
from src.analysis_tools import (
    ANALYSIS_TOOLS,
    get_kline_data,
    get_account_balance,
    get_market_ticker,
    get_latest_price,
    get_positions,
    calculate_risk_metrics
)

logger = setup_logger()

@dataclass
class ToolCall:
    """工具调用请求"""
    name: str
    parameters: Dict[str, Any]
    call_id: str = None

@dataclass  
class ToolResult:
    """工具调用结果"""
    call_id: str
    success: bool
    data: Any = None
    error_message: str = None

@dataclass
class PlanStep:
    """分析计划中的一个步骤"""
    step: int
    description: str
    status: str = "pending" # pending, in_progress, completed, failed
    result: Any = None

class PlanBasedAIOrchestrator:
    """
    基于计划的AI系统编排器
    
    职责：
    1. 强制AI首先生成分析计划。
    2. 严格按照计划步骤执行，调用工具并收集结果。
    3. 指导AI根据执行结果生成最终报告。
    """
    
    def __init__(self, config_path="config/enhanced_config.yaml"):
        """
        初始化AI编排器
        
        Args:
            config_path: 主配置文件路径
        """
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()
        
        self.ai_config = self.config.get('ai_analysis', {}).get('qwen', {})
        self.api_key: Optional[str] = None
        self.base_url = self.ai_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.model = self.ai_config.get('model', 'qwen-plus')
        
        self.system_prompt = self._load_system_prompt()
        self.tools_definition = self._load_tools_definition()
        
        self.tool_mapping = {
            'get_kline_data': get_kline_data,
            'get_market_ticker': get_market_ticker, 
            'get_latest_price': get_latest_price,
            'get_account_balance': get_account_balance,
            'get_positions': get_positions,
            'calculate_risk_metrics': calculate_risk_metrics
        }
        
        logger.info("Plan-Based AI Orchestrator initialized successfully")
    
    def _load_system_prompt(self) -> str:
        """加载AI系统提示词"""
        try:
            prompt_path = Path("config/AI_Trading_System_Prompt_V1.md")
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning("System prompt file not found, using default")
                return "您是一位专业的量化交易分析师。"
        except Exception as e:
            logger.error(f"Error loading system prompt: {e}")
            return "您是一位专业的量化交易分析师。"
    
    def _load_tools_definition(self) -> List[Dict]:
        """加载工具定义"""
        return ANALYSIS_TOOLS
    
    def _load_api_credentials(self):
        """加载API凭证"""
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        
        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY not found in environment variables. AI calls will be mocked.")
    
    def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """执行AI的工具调用请求"""
        try:
            tool_name = tool_call.name
            if tool_name not in self.tool_mapping:
                return ToolResult(call_id=tool_call.call_id, success=False, error_message=f"未授权的工具: {tool_name}")
            
            tool_function = self.tool_mapping[tool_name]
            
            logger.info(f"AI正在调用工具: {tool_name}")
            logger.info(f"工具参数: {json.dumps(tool_call.parameters, ensure_ascii=False, indent=2)}")
            
            # Execute the function with the provided parameters
            result_data = tool_function(**tool_call.parameters)
            
            logger.info(f"工具调用成功: {tool_name}")
            return ToolResult(call_id=tool_call.call_id, success=True, data=result_data)
            
        except Exception as e:
            error_msg = f"工具调用异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ToolResult(call_id=tool_call.call_id, success=False, error_message=error_msg)
    
    def send_ai_request(self, messages: List[Dict], tools: Optional[List[Dict]] = None, use_json_mode: bool = False) -> Dict:
        """发送请求给AI模型"""
        if not self.api_key:
            logger.warning("Mocking AI response as API key is not available.")
            # 根据请求类型返回不同的模拟响应
            if use_json_mode:
                # 模拟生成计划
                mock_plan = {
                    "plan": [
                        {"step": 1, "description": "获取BTC-USDT-SWAP的1小时K线数据"},
                        {"step": 2, "description": "获取账户余额"},
                        {"step": 3, "description": "生成最终报告"}
                    ]
                }
                return {
                    'choices': [{'message': {'content': json.dumps(mock_plan)}}]
                }
            elif any("tool_calls" in m for m in messages):
                 # 模拟工具调用后的响应
                return {
                    'choices': [{'message': {'content': '工具调用结果分析完成。'}}]
                }
            else:
                # 模拟最终报告
                return {
                    'choices': [{'message': {'content': '这是一个模拟生成的最终分析报告。'}}]
                }

        try:
            request_data = {
                "model": self.model,
                "messages": messages,
                "temperature": self.ai_config.get('temperature', 0.1),
                "max_tokens": self.ai_config.get('max_tokens', 4000)
            }
            
            if use_json_mode:
                request_data["response_format"] = {"type": "json_object"}

            if tools:
                request_data["tools"] = tools
                request_data["tool_choice"] = "auto"
            
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            
            response = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=request_data, timeout=self.ai_config.get('timeout', 60))
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"AI请求失败: {e}")
            raise

    def _generate_analysis_plan(self, analysis_request: str, context: Optional[Dict]) -> List[PlanStep]:
        """第一阶段：生成分析计划"""
        logger.info("--- 阶段一：生成分析计划 ---")
        
        plan_prompt = f"""
        分析请求: {analysis_request}

        上下文信息: {json.dumps(context, ensure_ascii=False, indent=2) if context else "无"}

        作为一名顶级的量化分析师，你的首要任务是为上述请求制定一个详细、分步的分析计划。
        请以JSON格式返回你的计划，计划应为一个包含多个步骤对象的列表。
        每个步骤对象应包含 'step' (整数) 和 'description' (字符串) 两个字段。
        你的计划需要逻辑清晰、步骤完整，确保最终能形成一份全面的分析报告。

        例如:
        {{
            "plan": [
                {{"step": 1, "description": "获取并分析BTC/USDT的1小时K线数据，识别近期趋势。"}},
                {{"step": 2, "description": "检查当前账户的持仓情况，判断是否有相关风险。"}},
                {{"step": 3, "description": "综合K线趋势和持仓情况，给出初步的交易建议。"}},
                {{"step": 4, "description": "总结所有发现，形成最终分析报告。" }}
            ]
        }}
        """

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": plan_prompt}
        ]

        ai_response = self.send_ai_request(messages, use_json_mode=True)
        plan_json_str = ai_response['choices'][0]['message']['content']
        
        try:
            plan_data = json.loads(plan_json_str)
            steps = [PlanStep(step=s['step'], description=s['description']) for s in plan_data.get('plan', [])]
            logger.info(f"成功生成分析计划，共 {len(steps)} 个步骤。")
            return steps
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"解析AI生成的计划失败: {e}")
            logger.error(f"收到的内容: {plan_json_str}")
            raise ValueError("AI未能生成有效的分析计划。")


    def _execute_plan_step(self, step: PlanStep, full_plan: List[PlanStep], executed_steps: List[PlanStep]) -> Any:
        """第二阶段：执行单个计划步骤"""
        logger.info(f"--- 阶段二：执行步骤 {step.step}: {step.description} ---")
        step.status = "in_progress"

        # 构建执行此步骤的提示
        execution_prompt = f"""
        当前正在执行分析计划的第 {step.step} 步。
        
        **完整计划概览:**
        {json.dumps([s.description for s in full_plan], ensure_ascii=False, indent=2)}

        **已完成的步骤和结果:**
        {json.dumps([{'step': s.step, 'description': s.description, 'result': s.result} for s in executed_steps], ensure_ascii=False, indent=2) if executed_steps else "无"}

        **当前任务:** {step.description}

        请严格围绕当前任务，调用必要的工具来获取数据并完成分析。
        在完成此步骤后，请直接输出此步骤的分析结论或数据结果。不要进行任何额外评论或总结。
        """

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": execution_prompt}
        ]
        
        openai_tools = self._convert_tools_to_openai_format()
        max_iterations = 5 # 单个步骤内的最大工具调用次数
        
        for i in range(max_iterations):
            ai_response = self.send_ai_request(messages, openai_tools)
            message = ai_response['choices'][0]['message']
            messages.append(message)

            tool_calls = message.get('tool_calls', [])
            if not tool_calls:
                logger.info(f"步骤 {step.step} 执行完成，无更多工具调用。")
                step.status = "completed"
                step.result = message.get('content', '无输出')
                return step.result

            # 执行工具调用
            for tool_call in tool_calls:
                function_call = tool_call['function']
                call_request = ToolCall(
                    name=function_call['name'],
                    parameters=json.loads(function_call['arguments']),
                    call_id=tool_call['id']
                )
                result = self.execute_tool_call(call_request)
                
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call['id'],
                    "content": json.dumps(result.data if result.success else {"error": result.error_message}, ensure_ascii=False)
                }
                messages.append(tool_message)
        
        step.status = "failed"
        step.result = "执行步骤时超出最大工具调用次数限制。"
        logger.error(step.result)
        return step.result


    def _generate_final_report(self, analysis_request: str, executed_plan: List[PlanStep]) -> str:
        """第三阶段：生成最终分析报告"""
        logger.info("--- 阶段三：生成最终分析报告 ---")

        report_prompt = f"""
        原始分析请求: {analysis_request}

        已按计划执行完所有分析步骤，以下是每一步的执行结果：
        {json.dumps([{'step': s.step, 'description': s.description, 'status': s.status, 'result': s.result} for s in executed_plan], ensure_ascii=False, indent=2)}

        现在，请你基于以上所有步骤的发现，撰写一份完整、详细、专业的最终分析报告。
        报告应结构清晰，全面回应用户的原始请求，并给出明确的结论和建议。
        """
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": report_prompt}
        ]

        ai_response = self.send_ai_request(messages)
        final_report = ai_response['choices'][0]['message']['content']
        logger.info("成功生成最终分析报告。")
        return final_report

    def analyze_market(self, analysis_request: str, context: Optional[Dict] = None) -> Dict:
        """
        执行完整的“计划-执行-报告”市场分析流程
        """
        try:
            self._load_api_credentials()
            
            # 阶段一：生成计划
            analysis_plan = self._generate_analysis_plan(analysis_request, context)
            if not analysis_plan:
                raise ValueError("未能生成有效的分析计划。")

            # 阶段二：执行计划
            executed_steps = []
            for step in analysis_plan:
                self._execute_plan_step(step, analysis_plan, executed_steps)
                executed_steps.append(step)
                if step.status == 'failed':
                    logger.error(f"步骤 {step.step} 执行失败，分析中止。")
                    break # 或者可以选择继续执行

            # 阶段三：生成报告
            final_report = self._generate_final_report(analysis_request, executed_steps)
            
            return {
                "success": True,
                "analysis_plan": [s.__dict__ for s in analysis_plan],
                "final_report": final_report,
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
            
        except Exception as e:
            logger.error(f"市场分析执行失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
    
    def _convert_tools_to_openai_format(self) -> List[Dict]:
        """将内部工具定义转换为OpenAI API格式"""
        return self.tools_definition

# 便利函数
def create_plan_based_orchestrator() -> PlanBasedAIOrchestrator:
    return PlanBasedAIOrchestrator()

def quick_plan_based_analysis(request: str, context: Optional[Dict] = None) -> Dict:
    orchestrator = create_plan_based_orchestrator()
    return orchestrator.analyze_market(request, context)