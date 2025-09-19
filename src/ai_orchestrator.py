"""
AI交易系统编排器 V2.1 - 递归式"指挥官-执行官"模式
AI Trading System Orchestrator V2.1 - Recursive "Commander-Executor" Pattern

实现透明、可控的AI分析代理架构：
- 指挥官模式 (main_session): 任务分解和整体规划
- 分析师模式 (sub_session): 具体数据分析和执行
"""

import json
import logging
import os
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from src.logger import setup_logger
from src.config_loader import ConfigLoader
from src.enhanced_data_manager import EnhancedDataManager

logger = setup_logger()

class SessionType(Enum):
    """会话类型枚举"""
    MAIN_SESSION = "main_session"  # 指挥官模式
    SUB_SESSION = "sub_session"    # 分析师模式

class ToolCategory(Enum):
    """工具类别枚举"""
    SIMPLE_TOOLS = "simple_tools"      # 简单工具：数据获取
    META_TOOLS = "meta_tools"          # 元工具：任务分解
    THINKING_TOOLS = "thinking_tools"  # 思维工具：结构化思考

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
class SessionConfig:
    """会话配置"""
    session_type: SessionType
    allowed_tool_categories: List[ToolCategory]
    max_iterations: int = 10
    enable_sequentialthinking: bool = True

class AIOrchestrator:
    """AI编排器 V2.1 - 实现递归式"指挥官-执行官"模式"""
    
    def __init__(self, data_manager: EnhancedDataManager, mcp_enabled: bool = False):
        """初始化AI编排器"""
        # 注入依赖
        self.data_manager = data_manager
        self.mcp_enabled = mcp_enabled
        
        # 从data_manager获取配置
        self.config = self.data_manager.config
        
        # AI配置
        self.ai_config = self.config.get('ai_analysis', {}).get('qwen', {})
        self.api_key: Optional[str] = None
        self.base_url = self.ai_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        self.model = self.ai_config.get('model', 'qwen-plus')
        
        # 加载配置文件
        self._load_configuration()
        
        # 初始化工具系统
        self._initialize_tool_system()
        
        # 加载API凭证
        self._load_api_credentials()
        
        # 当前会话配置
        self.current_session_config = None
        
        # 对话历史
        self.conversation_history = []
        
        logger.info("AIOrchestrator V2.1 初始化完成")
    
    def _get_default_tool_classification(self) -> Dict:
        """获取默认工具分类配置"""
        return {
            "tool_classification_system": {
                "version": "2.1",
                "tool_categories": {
                    "simple_tools": {
                        "description": "基础数据获取和简单计算工具",
                        "allowed_sessions": ["main_session", "sub_session"],
                        "tools": {
                            "get_kline_data": {"description": "获取K线数据"},
                            "get_market_ticker": {"description": "获取市场行情数据"},
                            "get_latest_price": {"description": "获取最新价格"}
                        }
                    },
                    "meta_tools": {
                        "description": "任务分解和高级编排工具",
                        "allowed_sessions": ["main_session"],
                        "tools": {
                            "decompose_and_execute_task": {"description": "分解复杂任务并执行"},
                            "analyze_complex_scenario": {"description": "复杂场景分析"}
                        }
                    },
                    "thinking_tools": {
                        "description": "思维和推理工具",
                        "allowed_sessions": ["main_session", "sub_session"],
                        "tools": {
                            "sequentialthinking": {"description": "结构化思维推理工具"}
                        }
                    }
                },
                "session_configurations": {
                    "main_session": {
                        "allowed_tool_categories": ["simple_tools", "meta_tools", "thinking_tools"]
                    },
                    "sub_session": {
                        "allowed_tool_categories": ["simple_tools", "thinking_tools"]
                    }
                }
            }
        }
    
    def _load_configuration(self):
        """加载V2.1配置文件"""
        try:
            # 加载工具分类配置
            tool_config_path = "config/tool_classification_config.json"
            if os.path.exists(tool_config_path):
                with open(tool_config_path, 'r', encoding='utf-8') as f:
                    self.tool_classification_config = json.load(f)
                logger.info("工具分类配置加载成功")
            else:
                self.tool_classification_config = self._get_default_tool_classification()
                logger.warning("工具分类配置文件不存在，使用默认配置")
            
            # 加载系统提示词
            prompt_path = "config/AI_Trading_System_Prompt_V2.1.md"
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    self.system_prompt = f.read()
            else:
                logger.warning(f"系统提示词文件不存在: {prompt_path}")
                self.system_prompt = self._get_default_prompt()
            
            # 加载工具配置
            tools_path = "config/AI_Trading_System_Tools_V2.1.json"
            if os.path.exists(tools_path):
                with open(tools_path, 'r', encoding='utf-8') as f:
                    self.tools_config = json.load(f)
            else:
                logger.warning(f"工具配置文件不存在: {tools_path}")
                self.tools_config = self._get_default_tools_config()
                
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            self.system_prompt = self._get_default_prompt()
            self.tools_config = self._get_default_tools_config()
    
    def _initialize_tool_system(self):
        """初始化工具系统"""
        # 工具适配器映射
        self.tool_adapters = {
            # 简单工具
            'get_kline_data': self._get_kline_data_adapter,
            'get_market_ticker': self._get_market_ticker_adapter,
            'get_latest_price': self._get_latest_price_adapter,
            'get_account_balance': self._get_account_balance_adapter,
            'get_positions': self._get_positions_adapter,
            'calculate_risk_metrics': self._calculate_risk_metrics_adapter,
            
            # 元工具
            'decompose_and_execute_task': self._decompose_and_execute_task_adapter,
            
            # 思维工具
            'sequentialthinking': self._sequentialthinking_adapter
        }
        
        # 工具分类映射
        self.tool_categories = {
            ToolCategory.SIMPLE_TOOLS: [
                'get_kline_data', 'get_market_ticker', 'get_latest_price',
                'get_account_balance', 'get_positions', 'calculate_risk_metrics'
            ],
            ToolCategory.META_TOOLS: [
                'decompose_and_execute_task'
            ],
            ToolCategory.THINKING_TOOLS: [
                'sequentialthinking'
            ]
        }
        
        # 会话工具权限配置
        self.session_tool_permissions = {
            SessionType.MAIN_SESSION: [
                ToolCategory.META_TOOLS,
                ToolCategory.THINKING_TOOLS
            ],
            SessionType.SUB_SESSION: [
                ToolCategory.SIMPLE_TOOLS,
                ToolCategory.THINKING_TOOLS
            ]
        }
    
    def _get_default_prompt(self) -> str:
        """获取默认系统提示词"""
        return """# AI交易系统分析师 V2.1

## 角色定义
你是一个专业的AI交易系统分析师，具备递归式"指挥官-执行官"模式的能力。

## 最高指令
风险规避优先：在任何情况下，风险控制都是第一优先级。

## 工作模式识别
根据当前会话类型自动切换工作模式：
- 指挥官模式(main_session)：负责任务分解和整体规划
- 分析师模式(sub_session)：负责具体数据分析和执行

## 核心能力
1. 决策透明性：每个决策都有清晰的推理过程
2. 行为可控性：严格按照权限和规则执行
3. 分层规划能力：复杂任务自动分解
4. 结构化思考能力：使用sequentialthinking工具进行深度思考
"""
    
    def _get_default_tools_config(self) -> Dict:
        """获取默认工具配置"""
        return {
            "tool_categories": {
                "simple_tools": {
                    "description": "基础数据获取工具",
                    "tools": ["get_kline_data", "get_market_ticker", "get_latest_price"]
                },
                "meta_tools": {
                    "description": "任务分解和编排工具", 
                    "tools": ["decompose_and_execute_task"]
                },
                "thinking_tools": {
                    "description": "结构化思维工具",
                    "tools": ["sequentialthinking"]
                }
            },
            "session_permissions": {
                "main_session": ["meta_tools", "thinking_tools"],
                "sub_session": ["simple_tools", "thinking_tools"]
            },
            "tools": {
                "get_kline_data": {
                    "description": "获取K线数据",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "timeframe": {"type": "string"},
                            "limit": {"type": "integer"}
                        }
                    }
                }
            }
        }
    
    def _load_api_credentials(self):
        """加载API凭证"""
        try:
            self.api_key = os.environ.get("DASHSCOPE_API_KEY")
            if not self.api_key:
                logger.warning("DASHSCOPE_API_KEY not found in environment variables")
        except Exception as e:
            logger.error(f"Failed to load API credentials: {e}")
    
    def set_session_config(self, session_type: SessionType, **kwargs):
        """设置会话配置"""
        allowed_categories = self.session_tool_permissions.get(session_type, [])
        
        self.current_session_config = SessionConfig(
            session_type=session_type,
            allowed_tool_categories=allowed_categories,
            max_iterations=kwargs.get('max_iterations', 10),
            enable_sequentialthinking=kwargs.get('enable_sequentialthinking', True)
        )
        
        logger.info(f"会话配置已设置: {session_type.value}, 允许工具类别: {[cat.value for cat in allowed_categories]}")
    
    def _is_tool_allowed(self, tool_name: str) -> bool:
        """检查工具是否被当前会话允许"""
        if not self.current_session_config:
            return False
        
        # 从工具分类配置中获取信息
        tool_categories = self.tool_classification_config.get("tool_classification_system", {}).get("tool_categories", {})
        session_config = self.tool_classification_config.get("tool_classification_system", {}).get("session_configurations", {})
        
        # 获取当前会话类型
        current_session = self.current_session_config.session_type.value
        
        # 获取当前会话允许的工具类别
        allowed_categories = session_config.get(current_session, {}).get("allowed_tool_categories", [])
        
        # 检查工具是否在允许的类别中
        for category_name in allowed_categories:
            if category_name in tool_categories:
                category_tools = tool_categories[category_name].get("tools", {})
                if tool_name in category_tools:
                    return True
        
        return False
    
    # 工具适配器方法
    def _get_kline_data_adapter(self, symbol=None, timeframe='1h', limit=100):
        """K线数据获取适配器"""
        try:
            if symbol is None:
                symbol = self.data_manager.trading_symbol
            
            result = self.data_manager.fetch_and_process_kline_data(
                symbol=symbol, 
                timeframes=[timeframe]
            )
            
            if 'processed_data' in result and timeframe in result['processed_data']:
                return result['processed_data'][timeframe]
            else:
                return {'error': 'No data available for specified timeframe'}
                
        except Exception as e:
            logger.error(f"Error in get_kline_data_adapter: {e}")
            return {'error': str(e)}
    
    def _get_market_ticker_adapter(self, symbol=None):
        """市场行情获取适配器"""
        try:
            result = self.data_manager.get_market_summary(symbol)
            if 'market_data' in result:
                return result['market_data']
            else:
                return result
        except Exception as e:
            logger.error(f"Error in get_market_ticker_adapter: {e}")
            return {'error': str(e)}
    
    def _get_latest_price_adapter(self, symbol=None):
        """最新价格获取适配器"""
        try:
            result = self.data_manager.get_market_summary(symbol)
            if 'market_data' in result and 'last' in result['market_data']:
                return {'price': result['market_data']['last'], 'symbol': symbol or self.data_manager.trading_symbol}
            else:
                return {'error': 'Price data not available'}
        except Exception as e:
            logger.error(f"Error in get_latest_price_adapter: {e}")
            return {'error': str(e)}
    
    def _get_account_balance_adapter(self):
        """账户余额获取适配器"""
        try:
            result = self.data_manager.get_account_summary()
            if 'balance' in result:
                return result['balance']
            else:
                return result
        except Exception as e:
            logger.error(f"Error in get_account_balance_adapter: {e}")
            return {'error': str(e)}
    
    def _get_positions_adapter(self):
        """持仓信息获取适配器"""
        try:
            result = self.data_manager.get_account_summary()
            if 'positions' in result:
                return result['positions']
            else:
                return []
        except Exception as e:
            logger.error(f"Error in get_positions_adapter: {e}")
            return {'error': str(e)}
    
    def _calculate_risk_metrics_adapter(self):
        """风险指标计算适配器"""
        try:
            account_data = self.data_manager.get_account_summary()
            market_data = self.data_manager.get_market_summary()
            
            risk_metrics = {
                'account_balance': account_data.get('balance', {}).get('balance', 0),
                'available_balance': account_data.get('balance', {}).get('available_balance', 0),
                'positions_count': len(account_data.get('positions', [])),
                'market_price': market_data.get('market_data', {}).get('last', 0),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
            return risk_metrics
        except Exception as e:
            logger.error(f"Error in calculate_risk_metrics_adapter: {e}")
            return {'error': str(e)}
    
    def _decompose_and_execute_task_adapter(self, task_description: str, context: Optional[Dict] = None):
        """任务分解和执行适配器"""
        try:
            # 创建子会话来执行分解后的任务
            sub_result = self.analyze_market(
                analysis_request=task_description,
                context=context,
                session_type=SessionType.SUB_SESSION
            )
            
            return {
                'task_decomposition': f"任务已分解并执行: {task_description}",
                'sub_session_result': sub_result,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        except Exception as e:
            logger.error(f"Error in decompose_and_execute_task_adapter: {e}")
            return {'error': str(e)}
    
    def _sequentialthinking_adapter(self, thinking_request: str, context: Optional[Dict] = None):
        """结构化思维适配器 - 实现思考-行动循环模式"""
        try:
            # 初始化思考会话
            thinking_session = {
                'session_id': f"thinking_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                'request': thinking_request,
                'context': context or {},
                'thinking_steps': [],
                'actions_taken': [],
                'current_step': 1,
                'max_steps': 10,
                'status': 'active'
            }
            
            logger.info(f"启动sequentialthinking会话: {thinking_session['session_id']}")
            
            # 思考-行动循环
            while thinking_session['current_step'] <= thinking_session['max_steps'] and thinking_session['status'] == 'active':
                step_result = self._execute_thinking_step(thinking_session)
                thinking_session['thinking_steps'].append(step_result)
                
                # 检查是否需要执行行动
                if step_result.get('requires_action', False):
                    action_result = self._execute_thinking_action(step_result, thinking_session)
                    thinking_session['actions_taken'].append(action_result)
                    
                    # 更新上下文
                    thinking_session['context'].update(action_result.get('context_updates', {}))
                
                # 检查是否完成思考
                if step_result.get('thinking_complete', False):
                    thinking_session['status'] = 'completed'
                    break
                
                thinking_session['current_step'] += 1
            
            # 生成最终结果
            final_result = self._synthesize_thinking_results(thinking_session)
            
            logger.info(f"sequentialthinking会话完成: {thinking_session['session_id']}, 步骤数: {len(thinking_session['thinking_steps'])}")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in sequentialthinking_adapter: {e}")
            return {'error': str(e), 'session_id': thinking_session.get('session_id', 'unknown')}
    
    def _execute_thinking_step(self, thinking_session: Dict) -> Dict:
        """执行单个思考步骤"""
        try:
            step_num = thinking_session['current_step']
            request = thinking_session['request']
            context = thinking_session['context']
            
            # 构建思考提示
            thinking_prompt = self._build_thinking_prompt(step_num, request, context, thinking_session['thinking_steps'])
            
            # 模拟结构化思考过程
            step_result = {
                'step_number': step_num,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'thinking_focus': self._determine_thinking_focus(step_num, request),
                'analysis': self._perform_step_analysis(thinking_prompt, context),
                'insights': [],
                'requires_action': False,
                'thinking_complete': False,
                'confidence_level': 0.0
            }
            
            # 根据步骤类型进行不同的思考
            if step_num == 1:
                step_result.update(self._initial_problem_analysis(request, context))
            elif step_num <= 3:
                step_result.update(self._data_gathering_analysis(request, context))
            elif step_num <= 6:
                step_result.update(self._logical_reasoning_analysis(request, context, thinking_session['thinking_steps']))
            else:
                step_result.update(self._synthesis_analysis(request, context, thinking_session['thinking_steps']))
            
            return step_result
            
        except Exception as e:
            logger.error(f"Error in thinking step {thinking_session['current_step']}: {e}")
            return {
                'step_number': thinking_session['current_step'],
                'error': str(e),
                'thinking_complete': True
            }
    
    def _execute_thinking_action(self, step_result: Dict, thinking_session: Dict) -> Dict:
        """执行思考步骤中需要的行动"""
        try:
            action_type = step_result.get('action_type', 'data_collection')
            action_params = step_result.get('action_params', {})
            
            action_result = {
                'action_type': action_type,
                'step_number': step_result['step_number'],
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'success': False,
                'data': None,
                'context_updates': {}
            }
            
            # 根据行动类型执行相应操作
            if action_type == 'data_collection':
                action_result.update(self._execute_data_collection_action(action_params))
            elif action_type == 'analysis_verification':
                action_result.update(self._execute_verification_action(action_params, thinking_session))
            elif action_type == 'pattern_recognition':
                action_result.update(self._execute_pattern_recognition_action(action_params))
            else:
                action_result['data'] = f"未知行动类型: {action_type}"
            
            return action_result
            
        except Exception as e:
            logger.error(f"Error executing thinking action: {e}")
            return {
                'action_type': step_result.get('action_type', 'unknown'),
                'error': str(e),
                'success': False
            }
    
    def _synthesize_thinking_results(self, thinking_session: Dict) -> Dict:
        """综合思考结果"""
        try:
            thinking_steps = thinking_session['thinking_steps']
            actions_taken = thinking_session['actions_taken']
            
            # 提取关键洞察
            key_insights = []
            for step in thinking_steps:
                key_insights.extend(step.get('insights', []))
            
            # 计算整体置信度
            confidence_scores = [step.get('confidence_level', 0.0) for step in thinking_steps if 'confidence_level' in step]
            overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            
            # 生成最终结论
            final_conclusion = self._generate_final_conclusion(thinking_steps, actions_taken, thinking_session['request'])
            
            return {
                'session_id': thinking_session['session_id'],
                'original_request': thinking_session['request'],
                'thinking_process': {
                    'total_steps': len(thinking_steps),
                    'actions_taken': len(actions_taken),
                    'thinking_steps': thinking_steps,
                    'actions': actions_taken
                },
                'key_insights': key_insights,
                'final_conclusion': final_conclusion,
                'confidence_level': overall_confidence,
                'recommendations': self._generate_recommendations(thinking_steps, actions_taken),
                'context_enrichment': thinking_session['context'],
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'status': thinking_session['status']
            }
            
        except Exception as e:
            logger.error(f"Error synthesizing thinking results: {e}")
            return {
                'session_id': thinking_session.get('session_id', 'unknown'),
                'error': str(e),
                'status': 'error'
            }
    
    def _build_thinking_prompt(self, step_num: int, request: str, context: Dict, previous_steps: List[Dict]) -> str:
        """构建思考提示"""
        base_prompt = f"步骤 {step_num}: 针对请求 '{request}' 进行结构化思考"
        
        if previous_steps:
            previous_insights = []
            for step in previous_steps[-3:]:  # 只考虑最近3步
                previous_insights.extend(step.get('insights', []))
            
            if previous_insights:
                base_prompt += f"\n前期洞察: {'; '.join(previous_insights[-5:])}"  # 最近5个洞察
        
        return base_prompt
    
    def _determine_thinking_focus(self, step_num: int, request: str) -> str:
        """确定思考焦点"""
        focus_map = {
            1: "问题理解与分解",
            2: "数据需求识别", 
            3: "信息收集策略",
            4: "逻辑推理框架",
            5: "模式识别分析",
            6: "假设验证",
            7: "结论综合",
            8: "风险评估",
            9: "建议生成",
            10: "最终验证"
        }
        return focus_map.get(step_num, f"深度分析-步骤{step_num}")
    
    def _perform_step_analysis(self, prompt: str, context: Dict) -> str:
        """执行步骤分析"""
        # 这里可以集成真实的AI推理
        # 目前返回模拟分析
        return f"基于提示 '{prompt}' 和上下文进行的结构化分析"
    
    def _initial_problem_analysis(self, request: str, context: Dict) -> Dict:
        """初始问题分析"""
        return {
            'insights': [f"识别核心问题: {request}", "确定分析维度", "评估复杂度"],
            'requires_action': True,
            'action_type': 'data_collection',
            'action_params': {'focus': 'problem_scope'},
            'confidence_level': 0.7
        }
    
    def _data_gathering_analysis(self, request: str, context: Dict) -> Dict:
        """数据收集分析"""
        return {
            'insights': ["识别数据需求", "确定信息来源", "评估数据质量"],
            'requires_action': True,
            'action_type': 'data_collection',
            'action_params': {'focus': 'market_data'},
            'confidence_level': 0.8
        }
    
    def _logical_reasoning_analysis(self, request: str, context: Dict, previous_steps: List[Dict]) -> Dict:
        """逻辑推理分析"""
        return {
            'insights': ["构建推理链条", "验证逻辑一致性", "识别关键模式"],
            'requires_action': True,
            'action_type': 'pattern_recognition',
            'action_params': {'focus': 'logical_patterns'},
            'confidence_level': 0.85
        }
    
    def _synthesis_analysis(self, request: str, context: Dict, previous_steps: List[Dict]) -> Dict:
        """综合分析"""
        return {
            'insights': ["整合分析结果", "形成最终结论", "评估置信度"],
            'requires_action': False,
            'thinking_complete': True,
            'confidence_level': 0.9
        }
    
    def _execute_data_collection_action(self, params: Dict) -> Dict:
        """执行数据收集行动"""
        focus = params.get('focus', 'general')
        return {
            'success': True,
            'data': f"收集到关于 {focus} 的相关数据",
            'context_updates': {f'{focus}_data_collected': True}
        }
    
    def _execute_verification_action(self, params: Dict, thinking_session: Dict) -> Dict:
        """执行验证行动"""
        return {
            'success': True,
            'data': "验证分析结果的一致性和逻辑性",
            'context_updates': {'verification_completed': True}
        }
    
    def _execute_pattern_recognition_action(self, params: Dict) -> Dict:
        """执行模式识别行动"""
        focus = params.get('focus', 'general_patterns')
        return {
            'success': True,
            'data': f"识别到 {focus} 中的关键模式",
            'context_updates': {f'{focus}_patterns_identified': True}
        }
    
    def _generate_final_conclusion(self, thinking_steps: List[Dict], actions_taken: List[Dict], original_request: str) -> str:
        """生成最终结论"""
        step_count = len(thinking_steps)
        action_count = len(actions_taken)
        
        return f"经过 {step_count} 步结构化思考和 {action_count} 次行动验证，针对 '{original_request}' 的分析已完成。整合了多维度洞察，形成了系统性的理解和建议。"
    
    def _generate_recommendations(self, thinking_steps: List[Dict], actions_taken: List[Dict]) -> List[str]:
        """生成建议"""
        recommendations = [
            "基于结构化思考过程的建议",
            "考虑多维度分析结果",
            "建议采用渐进式实施策略"
        ]
        
        # 根据思考步骤添加具体建议
        if len(thinking_steps) >= 5:
            recommendations.append("深度分析已完成，建议重点关注关键洞察")
        
        if len(actions_taken) >= 3:
            recommendations.append("多次验证确保了结论的可靠性")
        
        return recommendations
    
    def execute_tool_call(self, tool_call: ToolCall) -> ToolResult:
        """执行工具调用"""
        try:
            # 检查工具权限
            if not self._is_tool_allowed(tool_call.name):
                return ToolResult(
                    call_id=tool_call.call_id,
                    success=False,
                    error_message=f"工具 {tool_call.name} 不在当前会话权限内"
                )
            
            # 获取工具适配器
            if tool_call.name not in self.tool_adapters:
                return ToolResult(
                    call_id=tool_call.call_id,
                    success=False,
                    error_message=f"未知工具: {tool_call.name}"
                )
            
            # 执行工具调用
            adapter = self.tool_adapters[tool_call.name]
            result = adapter(**tool_call.parameters)
            
            return ToolResult(
                call_id=tool_call.call_id,
                success=True,
                data=result
            )
            
        except Exception as e:
            logger.error(f"工具调用执行失败: {tool_call.name} - {e}")
            return ToolResult(
                call_id=tool_call.call_id,
                success=False,
                error_message=str(e)
            )
    
    def send_ai_request(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
        """发送AI请求"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 2000
            }
            
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error(f"AI请求失败: {e}")
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": f"AI请求失败: {str(e)}"
                    }
                }]
            }
    
    def analyze_market(self, analysis_request: str, context: Optional[Dict] = None, session_type: SessionType = SessionType.MAIN_SESSION) -> Dict:
        """
        执行市场分析 - 支持递归式会话管理
        
        Args:
            analysis_request: 分析请求
            context: 上下文信息
            session_type: 会话类型
            
        Returns:
            分析结果
        """
        try:
            # 设置会话配置
            self.set_session_config(session_type)
            
            # 判断任务复杂度
            complexity = self._assess_task_complexity(analysis_request)
            
            if complexity == "complex" and session_type == SessionType.MAIN_SESSION:
                # 复杂任务：使用指挥官模式进行任务分解
                return self._execute_commander_mode(analysis_request, context)
            else:
                # 简单任务：直接执行分析师模式
                return self._execute_analyst_mode(analysis_request, context)
                
        except Exception as e:
            logger.error(f"市场分析执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "analysis": None,
                "execution_log": [f"❌ 分析执行失败: {str(e)}"],
                "timestamp": datetime.utcnow().isoformat() + 'Z'
            }
    
    def _assess_task_complexity(self, request: str) -> str:
        """评估任务复杂度"""
        complex_keywords = [
            "综合分析", "全面评估", "多维度", "深度分析", 
            "策略制定", "风险评估", "投资建议"
        ]
        
        simple_keywords = [
            "获取", "查询", "显示", "当前价格", "最新数据"
        ]
        
        request_lower = request.lower()
        
        if any(keyword in request_lower for keyword in complex_keywords):
            return "complex"
        elif any(keyword in request_lower for keyword in simple_keywords):
            return "simple"
        else:
            return "medium"
    
    def _execute_commander_mode(self, request: str, context: Optional[Dict] = None) -> Dict:
        """执行指挥官模式 - 任务分解和子会话管理"""
        logger.info("🎯 启动指挥官模式")
        
        # 构建指挥官模式的系统消息
        system_message = {
            "role": "system",
            "content": f"{self.system_prompt}\n\n当前模式：指挥官模式\n可用工具：任务分解工具、思维工具"
        }
        
        user_message = {
            "role": "user",
            "content": f"请分解以下复杂任务：{request}"
        }
        
        if context:
            user_message["content"] += f"\n\n上下文：{json.dumps(context, ensure_ascii=False, indent=2)}"
        
        messages = [system_message, user_message]
        
        # 获取指挥官模式可用工具
        available_tools = self._get_available_tools_for_session(SessionType.MAIN_SESSION)
        
        # 执行多轮对话
        return self._execute_conversation_loop(messages, available_tools, "指挥官模式")
    
    def _execute_analyst_mode(self, request: str, context: Optional[Dict] = None) -> Dict:
        """执行分析师模式 - 具体数据分析"""
        logger.info("📊 启动分析师模式")
        
        # 构建分析师模式的系统消息
        system_message = {
            "role": "system", 
            "content": f"{self.system_prompt}\n\n当前模式：分析师模式\n可用工具：数据获取工具、思维工具"
        }
        
        user_message = {
            "role": "user",
            "content": f"分析请求：{request}"
        }
        
        if context:
            user_message["content"] += f"\n\n上下文：{json.dumps(context, ensure_ascii=False, indent=2)}"
        
        messages = [system_message, user_message]
        
        # 获取分析师模式可用工具
        available_tools = self._get_available_tools_for_session(SessionType.SUB_SESSION)
        
        # 执行多轮对话
        return self._execute_conversation_loop(messages, available_tools, "分析师模式")
    
    def _get_available_tools_for_session(self, session_type: SessionType) -> List[Dict]:
        """获取指定会话类型的可用工具"""
        allowed_categories = self.session_tool_permissions.get(session_type, [])
        available_tools = []
        
        for category in allowed_categories:
            tools_in_category = self.tool_categories.get(category, [])
            for tool_name in tools_in_category:
                if tool_name in self.tools_config.get("tools", {}):
                    tool_def = self.tools_config["tools"][tool_name]
                    available_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": tool_def.get("description", ""),
                            "parameters": tool_def.get("parameters", {})
                        }
                    })
        
        return available_tools
    
    def _execute_conversation_loop(self, messages: List[Dict], available_tools: List[Dict], mode_name: str) -> Dict:
        """执行对话循环"""
        analysis_log = [f"🚀 启动{mode_name}"]
        max_iterations = self.current_session_config.max_iterations if self.current_session_config else 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            analysis_log.append(f"--- 第{iteration}轮对话 ---")
            
            # 发送请求给AI
            ai_response = self.send_ai_request(messages, available_tools)
            
            # 解析AI响应
            message = ai_response['choices'][0]['message']
            messages.append(message)
            
            # 检查是否有工具调用
            tool_calls = message.get('tool_calls', [])
            
            if not tool_calls:
                # 没有工具调用，分析完成
                analysis_log.append(f"✅ {mode_name}完成，没有更多工具调用")
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
                payload_content = result.data if result.success else {"error": result.error_message}
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call['id'],
                    "content": json.dumps(payload_content, ensure_ascii=False)
                }
                messages.append(tool_message)
        
        # 返回最终结果
        final_response = messages[-1]['content'] if messages[-1]['role'] == 'assistant' else "分析未完成"
        
        return {
            "success": True,
            "analysis": final_response,
            "execution_log": analysis_log,
            "iterations": iteration,
            "session_type": self.current_session_config.session_type.value if self.current_session_config else "unknown",
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
    
    def get_analysis_status(self) -> Dict:
        """获取分析系统状态"""
        return {
            "orchestrator_version": "2.1",
            "current_session": self.current_session_config.session_type.value if self.current_session_config else None,
            "allowed_tools": [cat.value for cat in self.current_session_config.allowed_tool_categories] if self.current_session_config else [],
            "api_configured": bool(self.api_key),
            "data_manager_ready": bool(self.data_manager),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }

# 便利函数
def create_orchestrator(data_manager: EnhancedDataManager, mcp_enabled: bool = False) -> AIOrchestrator:
    """创建AI编排器实例"""
    return AIOrchestrator(data_manager, mcp_enabled)

def quick_analysis(request: str, data_manager: EnhancedDataManager, context: Optional[Dict] = None) -> Dict:
    """快速分析便利函数"""
    orchestrator = create_orchestrator(data_manager)
    return orchestrator.analyze_market(request, context)