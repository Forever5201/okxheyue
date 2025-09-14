"""
消息队列系统 - 支持代理间异步通信
Message Queue System for Inter-Agent Communication

基于Untitled.md设计的事件驱动架构，实现代理间的消息传递
根据配置支持内存队列、Redis或RabbitMQ
"""

import json
import time
import uuid
import asyncio
import threading
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from src.logger import setup_logger

logger = setup_logger()

@dataclass
class Message:
    """消息类定义"""
    id: str
    topic: str
    payload: Dict[str, Any]
    timestamp: float
    sender: str
    ttl: int = 3600  # 消息生存时间（秒）
    retry_count: int = 0
    max_retries: int = 3
    
    def is_expired(self) -> bool:
        """检查消息是否过期"""
        return time.time() - self.timestamp > self.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

class MemoryMessageQueue:
    """
    内存消息队列实现
    支持发布/订阅模式，适用于开发和测试环境
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._topics: Dict[str, List[Message]] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
        self._running = False
        self._cleanup_interval = 300  # 5分钟清理一次过期消息
        self._executor = ThreadPoolExecutor(max_workers=4)
        
        # 初始化主题
        self._init_topics()
        
        logger.info("Memory Message Queue initialized")
    
    def _init_topics(self):
        """初始化配置的主题"""
        topics = self.config.get('topics', {})
        with self._lock:
            for topic_name, topic_path in topics.items():
                self._topics[topic_path] = []
                self._subscribers[topic_path] = []
        
        logger.info(f"Initialized {len(topics)} topics: {list(topics.values())}")
    
    def start(self):
        """启动消息队列"""
        if self._running:
            return
        
        self._running = True
        # 启动清理任务
        self._executor.submit(self._cleanup_task)
        logger.info("Message Queue started")
    
    def stop(self):
        """停止消息队列"""
        self._running = False
        self._executor.shutdown(wait=True)
        logger.info("Message Queue stopped")
    
    def publish(self, topic: str, payload: Dict[str, Any], sender: str = "system") -> str:
        """
        发布消息到指定主题
        
        Args:
            topic: 主题名称
            payload: 消息载荷
            sender: 发送者标识
            
        Returns:
            str: 消息ID
        """
        message_id = str(uuid.uuid4())
        ttl = self.config.get('message_ttl', 3600)
        max_retries = self.config.get('retry_attempts', 3)
        
        message = Message(
            id=message_id,
            topic=topic,
            payload=payload,
            timestamp=time.time(),
            sender=sender,
            ttl=ttl,
            max_retries=max_retries
        )
        
        with self._lock:
            if topic not in self._topics:
                self._topics[topic] = []
            
            self._topics[topic].append(message)
            
            # 异步通知订阅者
            if topic in self._subscribers:
                for callback in self._subscribers[topic]:
                    self._executor.submit(self._safe_callback, callback, message)
        
        logger.info(f"Published message {message_id} to topic '{topic}' from {sender}")
        return message_id
    
    def subscribe(self, topic: str, callback: Callable[[Message], None]) -> bool:
        """
        订阅主题消息
        
        Args:
            topic: 主题名称
            callback: 回调函数
            
        Returns:
            bool: 订阅是否成功
        """
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            
            self._subscribers[topic].append(callback)
        
        logger.info(f"Subscribed to topic '{topic}' with callback {callback.__name__}")
        return True
    
    def unsubscribe(self, topic: str, callback: Callable[[Message], None]) -> bool:
        """
        取消订阅
        
        Args:
            topic: 主题名称
            callback: 回调函数
            
        Returns:
            bool: 取消订阅是否成功
        """
        with self._lock:
            if topic in self._subscribers and callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)
                logger.info(f"Unsubscribed from topic '{topic}'")
                return True
        
        return False
    
    def get_messages(self, topic: str, limit: int = 100) -> List[Message]:
        """
        获取主题的消息列表
        
        Args:
            topic: 主题名称
            limit: 返回消息数量限制
            
        Returns:
            List[Message]: 消息列表
        """
        with self._lock:
            if topic not in self._topics:
                return []
            
            messages = [msg for msg in self._topics[topic] if not msg.is_expired()]
            return messages[-limit:] if len(messages) > limit else messages
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        with self._lock:
            stats = {
                'total_topics': len(self._topics),
                'total_subscribers': sum(len(subs) for subs in self._subscribers.values()),
                'topic_message_counts': {
                    topic: len([msg for msg in messages if not msg.is_expired()])
                    for topic, messages in self._topics.items()
                },
                'subscriber_counts': {
                    topic: len(subs) for topic, subs in self._subscribers.items()
                }
            }
        
        return stats
    
    def _safe_callback(self, callback: Callable, message: Message):
        """安全执行回调函数，处理异常"""
        try:
            callback(message)
        except Exception as e:
            logger.error(f"Error in message callback for topic '{message.topic}': {e}")
            
            # 消息重试逻辑
            if message.retry_count < message.max_retries:
                message.retry_count += 1
                # 延迟重试
                time.sleep(2 ** message.retry_count)  # 指数退避
                self._executor.submit(self._safe_callback, callback, message)
            else:
                logger.error(f"Message {message.id} failed after {message.max_retries} retries")
    
    def _cleanup_task(self):
        """清理过期消息的后台任务"""
        while self._running:
            try:
                with self._lock:
                    for topic in self._topics:
                        original_count = len(self._topics[topic])
                        self._topics[topic] = [
                            msg for msg in self._topics[topic] if not msg.is_expired()
                        ]
                        cleaned_count = original_count - len(self._topics[topic])
                        
                        if cleaned_count > 0:
                            logger.debug(f"Cleaned {cleaned_count} expired messages from topic '{topic}'")
                
                # 等待清理间隔
                time.sleep(self._cleanup_interval)
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                time.sleep(60)  # 错误时等待1分钟再重试

class MessageQueueManager:
    """
    消息队列管理器
    根据配置选择和管理不同类型的消息队列
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.queue_type = config.get('type', 'memory')
        self.queue = None
        
        self._init_queue()
    
    def _init_queue(self):
        """根据配置初始化消息队列"""
        if self.queue_type == 'memory':
            self.queue = MemoryMessageQueue(self.config)
        elif self.queue_type == 'redis':
            # TODO: 实现Redis消息队列
            logger.warning("Redis message queue not implemented yet, falling back to memory queue")
            self.queue = MemoryMessageQueue(self.config)
        elif self.queue_type == 'rabbitmq':
            # TODO: 实现RabbitMQ消息队列
            logger.warning("RabbitMQ message queue not implemented yet, falling back to memory queue")
            self.queue = MemoryMessageQueue(self.config)
        else:
            logger.error(f"Unsupported queue type: {self.queue_type}")
            raise ValueError(f"Unsupported queue type: {self.queue_type}")
        
        logger.info(f"Message Queue Manager initialized with {self.queue_type} queue")
    
    def start(self):
        """启动消息队列"""
        if self.queue:
            self.queue.start()
    
    def stop(self):
        """停止消息队列"""
        if self.queue:
            self.queue.stop()
    
    def publish(self, topic: str, payload: Dict[str, Any], sender: str = "system") -> str:
        """发布消息"""
        if not self.queue:
            raise RuntimeError("Message queue not initialized")
        return self.queue.publish(topic, payload, sender)
    
    def subscribe(self, topic: str, callback: Callable[[Message], None]) -> bool:
        """订阅消息"""
        if not self.queue:
            raise RuntimeError("Message queue not initialized")
        return self.queue.subscribe(topic, callback)
    
    def unsubscribe(self, topic: str, callback: Callable[[Message], None]) -> bool:
        """取消订阅"""
        if not self.queue:
            raise RuntimeError("Message queue not initialized")
        return self.queue.unsubscribe(topic, callback)
    
    def get_messages(self, topic: str, limit: int = 100) -> List[Message]:
        """获取消息"""
        if not self.queue:
            raise RuntimeError("Message queue not initialized")
        return self.queue.get_messages(topic, limit)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计信息"""
        if not self.queue:
            return {}
        return self.queue.get_queue_stats()