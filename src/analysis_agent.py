"""
分析代理 - 基于千问大模型的智能交易分析
Analysis Agent - Intelligent Trading Analysis with Qwen LLM

根据Untitled.md设计实现的分析代理，负责：
1. 订阅分析请求和重新分析触发消息
2. 通过工具调用循环获取和分析市场数据
3. 生成交易策略和监控触发器
4. 发布交易提案到消息队列
"""

import os
import json
import time
import asyncio
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from openai import OpenAI

from src.logger import setup_logger
from src.message_queue import MessageQueueManager, Message
from src.analysis_tools import AnalysisTools

logger = setup_logger()

class AnalysisAgent:
    """
    分析代理类
    实现基于千问大模型的智能交易分析功能
    """
    
    def __init__(self, config: Dict[str, Any], message_queue: MessageQueueManager):
        self.config = config
        self.agent_config = config.get('ai_analysis', {}).get('analysis_agent', {})
        self.ai_config = config.get('ai_analysis', {})
        self.qwen_config = self.ai_config.get('qwen', {})
        
        # 初始化千问客户端
        self.client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=self.qwen_config.get('base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        )
        
        # 消息队列和工具
        self.message_queue = message_queue
        self.analysis_tools = AnalysisTools(config)
        
        # 代理状态
        self.is_running = False
        self.current_tasks = {}  # 当前正在处理的任务
        self.max_concurrent_tasks = self.agent_config.get('max_concurrent_tasks', 2)
        
        # 消息主题配置
        self.topics = config.get('message_queue', {}).get('topics', {})
        
        logger.info("Analysis Agent initialized")
    
    def start(self):
        """启动分析代理"""
        if self.is_running:
            logger.warning("Analysis Agent is already running")
            return
        
        self.is_running = True
        
        # 订阅相关消息主题
        self._subscribe_to_topics()
        
        logger.info("Analysis Agent started and subscribed to topics")
    
    def stop(self):
        """停止分析代理"""
        self.is_running = False
        
        # 等待当前任务完成
        while self.current_tasks:
            time.sleep(0.1)
        
        logger.info("Analysis Agent stopped")
    
    def _subscribe_to_topics(self):
        """订阅相关的消息主题"""
        # 订阅分析请求消息 (用于开仓决策)
        analysis_request_topic = self.topics.get('analysis_request', 'analysis.request')
        self.message_queue.subscribe(analysis_request_topic, self._handle_analysis_request)
        
        # 订阅重新分析触发消息 (用于持仓管理)
        re_analysis_topic = self.topics.get('re_analysis_trigger', 'analysis.retrigger')
        self.message_queue.subscribe(re_analysis_topic, self._handle_re_analysis_trigger)
        
        logger.info(f"Subscribed to topics: {analysis_request_topic}, {re_analysis_topic}")
    
    def _handle_analysis_request(self, message: Message):
        """处理分析请求消息 (开仓分析)"""
        if not self.is_running:
            return
        
        if len(self.current_tasks) >= self.max_concurrent_tasks:
            logger.warning(f"Max concurrent tasks reached ({self.max_concurrent_tasks}), skipping analysis request")
            return
        
        task_id = f"analysis_{message.id}_{int(time.time())}"
        self.current_tasks[task_id] = message
        
        logger.info(f"Processing analysis request: {task_id}")
        
        # 在新线程中处理分析任务
        threading.Thread(
            target=self._process_analysis_task,
            args=(task_id, message, "opening_analysis"),
            daemon=True
        ).start()
    
    def _handle_re_analysis_trigger(self, message: Message):
        """处理重新分析触发消息 (持仓管理)"""
        if not self.is_running:
            return
        
        if len(self.current_tasks) >= self.max_concurrent_tasks:
            logger.warning(f"Max concurrent tasks reached ({self.max_concurrent_tasks}), skipping re-analysis")
            return
        
        task_id = f"reanalysis_{message.id}_{int(time.time())}"
        self.current_tasks[task_id] = message
        
        logger.info(f"Processing re-analysis trigger: {task_id}")
        
        # 在新线程中处理重新分析任务
        threading.Thread(
            target=self._process_analysis_task,
            args=(task_id, message, "position_management"),
            daemon=True
        ).start()
    
    def _process_analysis_task(self, task_id: str, message: Message, task_type: str):
        """
        处理分析任务的主要流程
        
        Args:
            task_id: 任务ID
            message: 触发消息
            task_type: 任务类型 ("opening_analysis" 或 "position_management")
        """
        try:
            logger.info(f"Starting analysis task {task_id} of type {task_type}")
            
            # 1. 从数据库读取最新的"近期学习总结" (暂时跳过，后续实现)
            learning_summary = self._get_latest_learning_summary()
            
            # 2. 启动分析会话
            analysis_result = self._run_analysis_session(task_type, message.payload, learning_summary)
            
            # 3. 发布交易提案
            if analysis_result.get('success', False):
                self._publish_trade_proposal(analysis_result['strategy'], task_type, task_id)
                logger.info(f"Analysis task {task_id} completed successfully")
            else:
                logger.error(f"Analysis task {task_id} failed: {analysis_result.get('error', 'Unknown error')}")
            
        except Exception as e:
            logger.error(f"Error processing analysis task {task_id}: {e}")
        finally:
            # 清理任务
            if task_id in self.current_tasks:
                del self.current_tasks[task_id]
    
    def _run_analysis_session(self, task_type: str, trigger_data: Dict[str, Any], learning_summary: str) -> Dict[str, Any]:
        """
        运行分析会话，实现LLM工具调用循环
        
        Args:
            task_type: 任务类型
            trigger_data: 触发数据
            learning_summary: 学习总结
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        try:
            # 构建初始系统提示
            system_prompt = self._build_system_prompt(task_type, learning_summary)
            
            # 构建初始用户消息
            user_message = self._build_initial_message(task_type, trigger_data)
            
            # 消息历史
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
            
            # 工具调用循环
            max_iterations = self.ai_config.get('analysis_agent', {}).get('max_tool_calls', 20)
            tools = self.analysis_tools.get_tool_schemas()
            
            for iteration in range(max_iterations):
                logger.debug(f"Analysis iteration {iteration + 1}/{max_iterations}")
                
                # 调用千问大模型
                response = self.client.chat.completions.create(
                    model=self.qwen_config.get('model', 'qwen-plus'),
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=self.qwen_config.get('temperature', 0.3),
                    max_tokens=self.qwen_config.get('max_tokens', 4000),
                    timeout=self.qwen_config.get('timeout', 60)
                )
                
                message = response.choices[0].message
                messages.append(message.to_dict())
                
                # 检查是否有工具调用
                if message.tool_calls:
                    # 执行工具调用
                    for tool_call in message.tool_calls:
                        tool_result = self._execute_tool_call(tool_call)
                        
                        # 添加工具调用结果到消息历史
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(tool_result, ensure_ascii=False)
                        })
                else:
                    # 没有工具调用，分析完成
                    final_content = message.content
                    strategy = self._parse_final_strategy(final_content, task_type)
                    
                    return {
                        "success": True,
                        "strategy": strategy,
                        "iterations": iteration + 1,
                        "final_response": final_content
                    }
            
            # 达到最大迭代次数
            logger.warning(f"Analysis reached max iterations ({max_iterations})")
            return {"success": False, "error": "Max iterations reached"}
            
        except Exception as e:
            logger.error(f"Error in analysis session: {e}")
            return {"success": False, "error": str(e)}
    
    def _execute_tool_call(self, tool_call) -> Dict[str, Any]:
        """执行工具调用"""
        try:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            
            logger.debug(f"Executing tool: {function_name} with args: {function_args}")
            
            # 调用分析工具
            result = self.analysis_tools.call_tool(function_name, **function_args)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool call: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_system_prompt(self, task_type: str, learning_summary: str) -> str:
        """构建系统提示"""
        base_prompt = """你是一个专业的加密货币交易分析师，具备深厚的技术分析和市场洞察能力。

你的职责：
1. 通过调用工具获取市场数据和技术指标
2. 进行全面的市场分析和风险评估
3. 生成具体的交易策略建议

可用工具：
- get_kline_data: 获取K线数据和技术指标
- get_account_balance: 查看账户余额
- get_positions: 查看当前持仓
- get_market_ticker: 获取市场行情
- calculate_indicators: 计算技术指标汇总
- get_timeframe_list: 获取可用时间周期
- analyze_trend: 分析多时间周期趋势

分析原则：
- 多时间周期分析：从短期到长期综合判断
- 技术指标结合：RSI、MACD、布林带等多指标验证
- 风险控制优先：明确止损和止盈位置
- 资金管理：合理的仓位大小和杠杆使用

"""
        
        if task_type == "opening_analysis":
            task_prompt = """
当前任务：开仓分析
目标：分析市场状况，判断是否适合开仓，如果适合则提供具体的开仓策略。

最终输出格式（JSON）：
{
    "action": "open_position" 或 "wait",
    "direction": "long" 或 "short" (如果action是open_position),
    "confidence": 0.0-1.0,
    "entry_price": 具体价格,
    "position_size": 建议仓位大小,
    "stop_loss": 止损价格,
    "take_profit": 止盈价格,
    "reasoning": "详细分析理由",
    "monitoring_triggers": [
        {
            "condition": "价格突破某个水平",
            "action": "平仓或调整止损",
            "price_level": 具体价格
        }
    ]
}
"""
        else:  # position_management
            task_prompt = """
当前任务：持仓管理
目标：分析当前持仓状况，决定是否需要调整或平仓。

最终输出格式（JSON）：
{
    "action": "hold", "close_position", "adjust_stop_loss", "partial_close",
    "confidence": 0.0-1.0,
    "reasoning": "详细分析理由",
    "new_stop_loss": 新止损价格 (如果需要调整),
    "close_percentage": 平仓比例 (如果部分平仓),
    "monitoring_triggers": [
        {
            "condition": "新的监控条件",
            "action": "对应操作",
            "price_level": 具体价格
        }
    ]
}
"""
        
        # 添加学习总结（如果有）
        learning_section = ""
        if learning_summary:
            learning_section = f"\n近期学习总结：\n{learning_summary}\n"
        
        return base_prompt + task_prompt + learning_section
    
    def _build_initial_message(self, task_type: str, trigger_data: Dict[str, Any]) -> str:
        """构建初始用户消息"""
        if task_type == "opening_analysis":
            return f"""请进行开仓分析。

触发信息：{json.dumps(trigger_data, ensure_ascii=False)}

请首先获取必要的市场数据和技术指标，然后进行全面分析，最后提供具体的交易建议。

开始分析："""
        else:  # position_management
            return f"""请进行持仓管理分析。

触发信息：{json.dumps(trigger_data, ensure_ascii=False)}

请首先获取当前持仓信息和市场数据，分析是否需要调整策略，然后提供具体建议。

开始分析："""
    
    def _parse_final_strategy(self, content: str, task_type: str) -> Dict[str, Any]:
        """解析最终策略输出"""
        try:
            # 尝试从响应中提取JSON
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                strategy_json = json.loads(json_match.group(1))
            else:
                # 尝试直接解析整个内容
                strategy_json = json.loads(content)
            
            # 添加元数据
            strategy_json['task_type'] = task_type
            strategy_json['timestamp'] = datetime.now().isoformat()
            strategy_json['agent'] = 'analysis_agent'
            
            return strategy_json
            
        except json.JSONDecodeError:
            logger.error(f"Failed to parse strategy JSON: {content}")
            return {
                "action": "wait",
                "confidence": 0.0,
                "reasoning": "解析策略失败",
                "raw_content": content,
                "task_type": task_type,
                "timestamp": datetime.now().isoformat(),
                "agent": "analysis_agent"
            }
    
    def _publish_trade_proposal(self, strategy: Dict[str, Any], task_type: str, task_id: str):
        """发布交易提案到消息队列"""
        try:
            proposal = {
                "strategy": strategy,
                "task_type": task_type,
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
                "agent": "analysis_agent"
            }
            
            # 发布到交易提案主题
            trade_proposal_topic = self.topics.get('trade_proposal', 'trade.proposal')
            message_id = self.message_queue.publish(
                topic=trade_proposal_topic,
                payload=proposal,
                sender="analysis_agent"
            )
            
            logger.info(f"Published trade proposal {message_id} to topic {trade_proposal_topic}")
            
        except Exception as e:
            logger.error(f"Error publishing trade proposal: {e}")
    
    def _get_latest_learning_summary(self) -> str:
        """
        获取最新的学习总结
        TODO: 从数据库或文件系统读取复盘代理生成的学习总结
        """
        # 暂时返回空字符串，后续实现数据库集成时完善
        return ""
    
    def get_status(self) -> Dict[str, Any]:
        """获取代理状态"""
        return {
            "is_running": self.is_running,
            "current_tasks": len(self.current_tasks),
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "task_list": list(self.current_tasks.keys())
        }