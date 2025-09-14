"""
AI交易系统编排器 - 项目经理模式
AI Trading System Orchestrator - Project Manager Pattern

实现透明、可控的AI分析代理架构：
- 项目经理 (Python代码): 管理整个流程，控制节奏，验证结果
- AI分析师 (AI模型): 在安全环境中思考，向项目经理请求数据和工具
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

class AIOrchestrator:
    """
    AI系统编排器 - 项目经理模式
    
    职责：
    1. 加载AI行为准则和工具定义
    2. 管理与AI模型的对话循环
    3. 翻译AI工具请求到本地MCP服务调用
    4. 验证和审核AI的分析结果
    """
    
    def __init__(self, config_path="config/enhanced_config.yaml"):
        """
        初始化AI编排器
        
        Args:
            config_path: 主配置文件路径
        """
        # 加载系统配置
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()
        
        # AI配置
        self.ai_config = self.config.get('ai_analysis', {}).get('qwen', {})
        self.api_key = None  # 将从环境变量加载
        self.base_url = self.ai_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.model = self.ai_config.get('model', 'qwen-plus')
        
        # MCP服务配置
        self.mcp_config = self.config.get('mcp_service', {})
        self.mcp_host = self.mcp_config.get('host', 'localhost')
        self.mcp_port = self.mcp_config.get('port', 5000)
        self.mcp_api_key = None  # 将从环境变量加载
        
        # 加载AI配置文件
        self.system_prompt = self._load_system_prompt()
        self.tools_definition = self._load_tools_definition()
        
        # 对话历史
        self.conversation_history = []
        
        # 工具映射表：AI工具名 -> MCP端点
        self.tool_mapping = {
            'get_kline_data': '/get_kline',
            'get_market_ticker': '/get_market_ticker', 
            'get_latest_price': '/get_latest_price',
            'get_account_balance': '/get_account_balance',
            'get_positions': '/get_positions',
            'calculate_risk_metrics': '/calculate_risk_metrics'
        }
        
        logger.info("AI Orchestrator initialized successfully")
    
    def _load_system_prompt(self) -> str:
        """加载AI系统提示词"""
        try:
            prompt_path = Path("config/ai_trading_system_prompt.md")
            if prompt_path.exists():
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                logger.warning("System prompt file not found, using default")
                return "您是一位专业的量化交易分析师。"
        except Exception as e:
            logger.error(f"Error loading system prompt: {e}")
            return "您是一位专业的量化交易分析师。"
    
    def _load_tools_definition(self) -> Dict:
        """加载工具定义"""
        try:
            tools_path = Path("config/ai_trading_system_tools.json")
            if tools_path.exists():
                with open(tools_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning("Tools definition file not found")
                return {"tools": []}
        except Exception as e:
            logger.error(f"Error loading tools definition: {e}")
            return {"tools": []}
    
    def _load_api_credentials(self):
        """加载API凭证"""
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.mcp_api_key = os.getenv("MCP_API_KEY")
        
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY not found in environment variables")
        if not self.mcp_api_key:
            raise ValueError("MCP_API_KEY not found in environment variables")
    
    def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """
        执行AI的工具调用请求
        
        Args:
            tool_call: AI的工具调用请求
            
        Returns:
            工具调用结果
        """
        try:
            tool_name = tool_call.name
            
            # 检查工具是否在授权列表中
            if tool_name not in self.tool_mapping:
                return ToolResult(
                    call_id=tool_call.call_id,
                    success=False,
                    error_message=f"未授权的工具: {tool_name}"
                )
            
            # 获取MCP端点
            mcp_endpoint = self.tool_mapping[tool_name]
            
            # 构建MCP请求
            mcp_url = f"http://{self.mcp_host}:{self.mcp_port}{mcp_endpoint}"
            headers = {
                "Content-Type": "application/json",
                "X-API-Key": self.mcp_api_key
            }
            
            # 记录工具调用
            logger.info(f"AI正在调用工具: {tool_name} -> {mcp_endpoint}")
            logger.info(f"工具参数: {json.dumps(tool_call.parameters, ensure_ascii=False, indent=2)}")
            
            # 发送请求到MCP服务
            if mcp_endpoint in ['/get_kline']:
                # POST请求
                response = requests.post(mcp_url, 
                                       headers=headers,
                                       json=tool_call.parameters,
                                       timeout=30)
            else:
                # GET请求
                response = requests.get(mcp_url,
                                      headers=headers,
                                      params=tool_call.parameters,
                                      timeout=30)
            
            response.raise_for_status()
            result_data = response.json()
            
            # 成功返回结果
            logger.info(f"工具调用成功: {tool_name}")
            return ToolResult(
                call_id=tool_call.call_id,
                success=True,
                data=result_data
            )
            
        except requests.exceptions.RequestException as e:
            error_msg = f"MCP服务调用失败: {str(e)}"
            logger.error(error_msg)
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                error_message=error_msg
            )
        except Exception as e:
            error_msg = f"工具调用异常: {str(e)}"
            logger.error(error_msg)
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                error_message=error_msg
            )
    
    def send_ai_request(self, messages: List[Dict], tools: List[Dict] = None) -> Dict:
        """
        发送请求给AI模型
        
        Args:
            messages: 对话消息列表
            tools: 可用工具列表
            
        Returns:
            AI模型的响应
        """
        try:
            # 构建请求数据
            request_data = {
                "model": self.model,
                "messages": messages,
                "temperature": self.ai_config.get('temperature', 0.3),
                "max_tokens": self.ai_config.get('max_tokens', 4000)
            }
            
            # 如果提供了工具，添加到请求中
            if tools:
                request_data["tools"] = tools
                request_data["tool_choice"] = "auto"
            
            # 发送请求
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=request_data,
                timeout=self.ai_config.get('timeout', 60)
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"AI请求失败: {e}")
            raise
    
    def analyze_market(self, analysis_request: str, context: Dict = None) -> Dict:
        """
        执行市场分析请求
        
        Args:
            analysis_request: 分析请求描述
            context: 可选的上下文信息
            
        Returns:
            分析结果和执行日志
        """
        try:
            # 加载API凭证
            self._load_api_credentials()
            
            # 构建系统消息
            system_message = {
                "role": "system",
                "content": self.system_prompt
            }
            
            # 构建用户请求
            user_message = {
                "role": "user", 
                "content": f"分析请求：{analysis_request}"
            }
            
            if context:
                user_message["content"] += f"\n\n上下文信息：{json.dumps(context, ensure_ascii=False, indent=2)}"
            
            # 初始化对话
            messages = [system_message, user_message]
            
            # 转换工具定义为OpenAI格式
            openai_tools = self._convert_tools_to_openai_format()
            
            # 执行多轮对话
            analysis_log = []
            max_iterations = 10  # 防止无限循环
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                analysis_log.append(f"--- 第{iteration}轮对话 ---")
                
                # 发送请求给AI
                ai_response = self.send_ai_request(messages, openai_tools)
                
                # 解析AI响应
                message = ai_response['choices'][0]['message']
                messages.append(message)
                
                # 检查是否有工具调用
                tool_calls = message.get('tool_calls', [])
                
                if not tool_calls:
                    # 没有工具调用，分析完成
                    analysis_log.append("✅ AI分析完成，没有更多工具调用")
                    break
                
                # 执行工具调用
                tool_results = []
                for tool_call in tool_calls:
                    function_call = tool_call['function']
                    
                    # 创建工具调用对象
                    call_request = ToolCall(
                        name=function_call['name'],
                        parameters=json.loads(function_call['arguments']),
                        call_id=tool_call['id']
                    )
                    
                    # 执行工具调用
                    result = self.execute_tool_call(call_request)
                    tool_results.append(result)
                    
                    # 记录到分析日志
                    if result.success:
                        analysis_log.append(f"🔧 工具调用成功: {call_request.name}")
                    else:
                        analysis_log.append(f"❌ 工具调用失败: {call_request.name} - {result.error_message}")
                
                # 将工具结果添加到消息中
                for tool_call, result in zip(tool_calls, tool_results):
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call['id'],
                        "content": json.dumps(result.data if result.success else {"error": result.error_message}, ensure_ascii=False)
                    }
                    messages.append(tool_message)
            
            # 返回最终结果
            final_response = messages[-1]['content'] if messages[-1]['role'] == 'assistant' else "分析未完成"
            
            return {
                "success": True,
                "analysis": final_response,
                "execution_log": analysis_log,
                "iterations": iteration,
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
            
        except Exception as e:
            logger.error(f"市场分析执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis": None,
                "execution_log": [f"❌ 分析执行失败: {str(e)}"],
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
    
    def _convert_tools_to_openai_format(self) -> List[Dict]:
        """将内部工具定义转换为OpenAI API格式"""
        openai_tools = []
        
        for tool in self.tools_definition.get('tools', []):
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool['name'],
                    "description": tool['description'],
                    "parameters": tool['parameters']
                }
            }
            openai_tools.append(openai_tool)
        
        return openai_tools
    
    def get_analysis_status(self) -> Dict:
        """获取分析系统状态"""
        return {
            "orchestrator_status": "active",
            "ai_model": self.model,
            "mcp_service": f"{self.mcp_host}:{self.mcp_port}",
            "available_tools": list(self.tool_mapping.keys()),
            "system_prompt_loaded": bool(self.system_prompt),
            "tools_definition_loaded": bool(self.tools_definition.get('tools')),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }

# 便利函数：快速创建分析实例
def create_orchestrator() -> AIOrchestrator:
    """创建AI编排器实例"""
    return AIOrchestrator()

def quick_analysis(request: str, context: Dict = None) -> Dict:
    """快速执行分析请求"""
    orchestrator = create_orchestrator()
    return orchestrator.analyze_market(request, context)