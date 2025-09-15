"""
AI交易系统编排器 - 项目经理模式
AI Trading System Orchestrator - Project Manager Pattern

实现透明、可控的AI分析代理架构：
- 项目经理 (Python代码): 管理整个流程，控制节奏，验证结果
- AI分析师 (AI模型): 在安全环境中思考，向项目经理请求数据和工具
"""

import json
import logging
import os
import time
import uuid
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
    name: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None

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
        self.api_key: Optional[str] = None  # 将从环境变量加载
        self.base_url = self.ai_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.model = self.ai_config.get('model', 'qwen-plus')
        
        # MCP服务配置
        self.mcp_config = self.config.get('mcp_service', {})
        self.mcp_host = self.mcp_config.get('host', 'localhost')
        self.mcp_port = self.mcp_config.get('port', 5000)
        self.mcp_api_key: Optional[str] = None  # 将从环境变量加载
        
        # 分析代理预算与约束配置
        self.agent_config = self.config.get('ai_analysis', {}).get('analysis_agent', {})
        self.max_tool_calls = int(self.agent_config.get('max_tool_calls', 20))
        self.analysis_timeout_seconds = int(self.agent_config.get('analysis_timeout', 300))
        self.observability = self.agent_config.get('observability', {})
        self.log_prompt_meta: bool = bool(self.observability.get('log_prompt_meta', False))
        self.prompt_preview_chars: int = int(self.observability.get('preview_chars', 0))
        self.audit_to_system_logs: bool = bool(self.observability.get('audit_to_system_logs', True))

        # 加载AI配置文件
        self.system_prompt = self._load_system_prompt()
        self.tools_definition = self._load_tools_definition()
        self.tool_param_schemas = {
            t.get('name'): t.get('parameters') for t in self.tools_definition.get('tools', [])
        }
        self.tool_return_schemas = {
            t.get('name'): t.get('returns') for t in self.tools_definition.get('tools', [])
        }
        
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
        
        # 尝试加载 JSON Schema 校验库
        try:
            from jsonschema import Draft7Validator  # noqa: F401
            self._jsonschema_available = True
        except Exception:
            self._jsonschema_available = False
            logger.warning("jsonschema not available; tool parameter validation will be basic only")
    
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
    
    def _load_tools_definition(self) -> Dict:
        """加载工具定义"""
        try:
            tools_path = Path("config/AI_Trading_System_Tools.json")
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
            
            # 工具入参 Schema 校验
            try:
                self._validate_tool_parameters(tool_name, tool_call.parameters)
            except Exception as ve:
                logger.error(f"工具参数校验失败: {ve}")
                return ToolResult(
                    call_id=tool_call.call_id,
                    success=False,
                    error_message=f"参数不符合工具契约: {ve}",
                    name=tool_name,
                    parameters=tool_call.parameters
                )

            # 根据契约转换参数到 MCP 端点实际需要的格式
            outgoing_params: Dict[str, Any] = dict(tool_call.parameters or {})
            if tool_name == 'get_kline_data' and mcp_endpoint == '/get_kline':
                try:
                    timeframe = outgoing_params.get('timeframe')
                    limit = int(outgoing_params.get('limit', 100))
                    limit = max(1, min(limit, 300))
                    mapped_name = self._map_timeframe_to_authorized_filename(timeframe)
                    outgoing_params = {
                        'name': mapped_name,
                        'max_bars': limit
                    }
                except Exception as map_err:
                    return ToolResult(
                        call_id=tool_call.call_id,
                        success=False,
                        error_message=f"时间周期映射失败: {map_err}",
                        name=tool_name,
                        parameters=tool_call.parameters
                    )

            # 发起请求
            start_ms = time.perf_counter()
            # 发送请求到MCP服务
            if mcp_endpoint in ['/get_kline']:
                # POST请求
                response = requests.post(
                    mcp_url,
                    headers=headers,
                    json=outgoing_params,
                    timeout=30
                )
            else:
                # GET请求
                response = requests.get(
                    mcp_url,
                    headers=headers,
                    params=outgoing_params,
                    timeout=30
                )
            
            response.raise_for_status()
            result_data = response.json()

            # 工具返回 Schema 校验
            try:
                self._validate_tool_returns(tool_name, result_data)
            except Exception as ve:
                logger.error(f"工具返回校验失败: {ve}")
                return ToolResult(
                    call_id=tool_call.call_id,
                    success=False,
                    error_message=f"返回不符合工具契约: {ve}",
                    name=tool_name,
                    parameters=outgoing_params
                )
            
            # 成功返回结果
            logger.info(f"工具调用成功: {tool_name}")
            latency_ms = (time.perf_counter() - start_ms) * 1000.0
            return ToolResult(
                call_id=tool_call.call_id,
                success=True,
                data=result_data,
                name=tool_name,
                parameters=outgoing_params,
                latency_ms=latency_ms,
                status_code=response.status_code
            )
            
        except requests.exceptions.RequestException as e:
            error_msg = f"MCP服务调用失败: {str(e)}"
            logger.error(error_msg)
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                error_message=error_msg,
                name=tool_call.name,
                parameters=tool_call.parameters
            )
        except Exception as e:
            error_msg = f"工具调用异常: {str(e)}"
            logger.error(error_msg)
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                error_message=error_msg,
                name=tool_call.name,
                parameters=tool_call.parameters
            )
    
    def send_ai_request(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
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
    
    def analyze_market(self, analysis_request: str, context: Optional[Dict] = None) -> Dict:
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
            analysis_log: List[str] = []
            max_iterations = 10
            iteration = 0
            tool_calls_used = 0
            run_start_time = time.time()
            run_id = str(uuid.uuid4())
            token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            tool_call_records: List[Dict[str, Any]] = []

            # 记录提示词元信息（脱敏）
            try:
                if self.log_prompt_meta:
                    sp = self.system_prompt or ""
                    import hashlib
                    prompt_hash = hashlib.sha256(sp.encode('utf-8')).hexdigest()[:16]
                    preview = sp[: self.prompt_preview_chars] if self.prompt_preview_chars > 0 else ""
                    analysis_log.append(
                        f"Prompt meta: len={len(sp)}, sha256[0:16]={prompt_hash}, preview={preview!r}"
                    )
            except Exception:
                pass
            
            while iteration < max_iterations:
                iteration += 1
                analysis_log.append(f"--- 第{iteration}轮对话 ---")
                if (time.time() - run_start_time) > self.analysis_timeout_seconds:
                    analysis_log.append("⏱️ 达到分析总时长限制，提前结束")
                    break
                
                # 发送请求给AI
                ai_response = self.send_ai_request(messages, openai_tools)

                # 累计 token 用量（如可用）
                try:
                    usage = ai_response.get('usage') or {}
                    token_usage['prompt_tokens'] += int(usage.get('prompt_tokens', 0))
                    token_usage['completion_tokens'] += int(usage.get('completion_tokens', 0))
                    token_usage['total_tokens'] += int(usage.get('total_tokens', usage.get('prompt_tokens', 0) + usage.get('completion_tokens', 0)))
                except Exception:
                    pass
                
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
                    if tool_calls_used >= self.max_tool_calls:
                        analysis_log.append("🧮 已达到max_tool_calls限制，停止执行更多工具调用")
                        break
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
                    tool_calls_used += 1
                    tool_call_records.append({
                        "name": result.name or call_request.name,
                        "parameters": result.parameters or call_request.parameters,
                        "success": result.success,
                        "latency_ms": result.latency_ms,
                        "status_code": result.status_code,
                        "call_id": result.call_id
                    })
                    
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
            final_text = messages[-1]['content'] if messages[-1]['role'] == 'assistant' else "分析未完成"
            structured_output = self._structure_final_analysis(final_text, tool_call_records)
            
            result_payload = {
                "success": True,
                "analysis": structured_output,
                "execution_log": analysis_log,
                "iterations": iteration,
                "tool_calls_used": tool_calls_used,
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "run_id": run_id,
                "token_usage": token_usage
            }

            # 写入系统运行摘要
            if self.audit_to_system_logs:
                try:
                    # 附加 prompt 元信息到摘要
                    sp = self.system_prompt or ""
                    import hashlib
                    prompt_meta = {
                        "length": len(sp),
                        "sha256_16": hashlib.sha256(sp.encode('utf-8')).hexdigest()[:16]
                    }
                    if self.prompt_preview_chars > 0:
                        prompt_meta["preview"] = sp[: self.prompt_preview_chars]
                    result_payload["prompt_meta"] = prompt_meta
                    self._write_run_summary(run_id, result_payload)
                except Exception as werr:
                    logger.warning(f"写入运行摘要失败: {werr}")

            return result_payload
            
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
    
    def _validate_tool_parameters(self, tool_name: str, params: Dict[str, Any]):
        """根据 tools_definition 对工具入参进行校验。jsonschema 可用则严格校验，否则做基本必填检查。"""
        schema = self.tool_param_schemas.get(tool_name)
        if not schema:
            return
        if self._jsonschema_available:
            try:
                from jsonschema import validate
                validate(instance=params or {}, schema=schema)
            except Exception as e:
                raise ValueError(str(e))
        else:
            required = (schema or {}).get('required', [])
            for key in required:
                if key not in (params or {}):
                    raise ValueError(f"缺少必填参数: {key}")
    
    def _validate_tool_returns(self, tool_name: str, result: Any):
        """根据 tools_definition 对工具返回进行校验。"""
        schema = self.tool_return_schemas.get(tool_name)
        if not schema:
            return
        if self._jsonschema_available:
            try:
                from jsonschema import validate
                validate(instance=result, schema=schema)
            except Exception as e:
                raise ValueError(str(e))
        else:
            # 基础校验：如果是对象并声明了properties，则检查关键字段存在
            if isinstance(result, dict):
                properties = (schema or {}).get('properties', {})
                for key in properties.keys():
                    if key not in result:
                        # 仅对关键输出字段做基本要求
                        if tool_name == 'get_kline_data' and key in ('data', 'metadata'):
                            raise ValueError(f"缺少关键返回字段: {key}")
    
    def _map_timeframe_to_authorized_filename(self, timeframe: str) -> str:
        """把 timeframe 映射到 manifest.json 白名单文件名。优先读取 manifest 校验。"""
        if not timeframe:
            raise ValueError("timeframe 为空")
        tf = str(timeframe).lower()
        storage_dir = self.config.get('storage', {}).get('base_directory', 'kline_data')
        manifest_path = Path(storage_dir) / 'manifest.json'
        candidate = f"{tf}/{tf}.csv"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                files = set(manifest.get('files', []))
                if candidate in files:
                    return candidate
                else:
                    raise ValueError(f"文件未授权: {candidate}")
            except Exception as e:
                raise ValueError(f"读取manifest失败: {e}")
        return candidate
    
    def _structure_final_analysis(self, content: str, tool_call_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """把最终回答整理为固定结构，便于前端与审计使用。"""
        def extract_section(text: str, marker: str) -> Optional[str]:
            if marker in text:
                start = text.find(marker)
                next_markers = [m for m in ["📊", "⚠️", "💡", "🔄", "📋"] if m != marker and m in text]
                ends = [text.find(m, start + 1) for m in next_markers]
                ends = [e for e in ends if e != -1]
                end = min(ends) if ends else len(text)
                return text[start:end].strip()
            return None

        analysis_plan = extract_section(content, "📋")
        analysis_report = extract_section(content, "📊")
        risk_assessment = extract_section(content, "⚠️")
        actionable_advice = extract_section(content, "💡")
        monitoring_notes = extract_section(content, "🔄")

        return {
            "analysis_plan": analysis_plan,
            "analysis_report": analysis_report,
            "risk_assessment": risk_assessment,
            "actionable_advice": actionable_advice,
            "monitoring_notes": monitoring_notes,
            "tool_calls": tool_call_records,
            "raw": content,
            "compliance_flags": {
                "has_analysis_plan": bool(analysis_plan),
                "has_analysis_report": bool(analysis_report),
                "has_risk_assessment": bool(risk_assessment),
                "has_actionable_advice": bool(actionable_advice)
            }
        }

    def _write_run_summary(self, run_id: str, payload: Dict[str, Any]):
        """把本次分析运行摘要写入 system_logs，并更新 latest_run_summary.json。"""
        system_logs_dir = Path('system_logs')
        system_logs_dir.mkdir(exist_ok=True)
        timestamp_str = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        out_file = system_logs_dir / f"analysis_summary_{timestamp_str}.json"
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        latest_path = system_logs_dir / 'latest_run_summary.json'
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    
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

def quick_analysis(request: str, context: Optional[Dict] = None) -> Dict:
    """快速执行分析请求"""
    orchestrator = create_orchestrator()
    return orchestrator.analyze_market(request, context)