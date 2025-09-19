#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIOrchestrator V2.1 性能优化测试
测试会话管理和工具调用的性能表现
"""

import time
import asyncio
import threading
import psutil
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum

# 简化的枚举和数据类
class SessionType(Enum):
    MAIN_SESSION = "main_session"
    SUB_SESSION = "sub_session"

class ToolCategory(Enum):
    SIMPLE_TOOLS = "simple_tools"
    META_TOOLS = "meta_tools"
    THINKING_TOOLS = "thinking_tools"

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    operation_name: str
    start_time: float
    end_time: float
    duration: float
    memory_usage: float
    cpu_usage: float
    success: bool
    error_message: Optional[str] = None

@dataclass
class SessionMetrics:
    """会话性能指标"""
    session_id: str
    session_type: SessionType
    creation_time: float
    destruction_time: Optional[float]
    total_tools_called: int
    memory_peak: float
    cpu_peak: float

class PerformanceOptimizationTester:
    """性能优化测试器"""
    
    def __init__(self):
        self.metrics: List[PerformanceMetrics] = []
        self.session_metrics: List[SessionMetrics] = []
        self.process = psutil.Process()
        
        # 模拟AIOrchestrator配置
        self.config = {
            "max_sessions": 10,
            "session_timeout": 300,
            "tool_cache_size": 100,
            "thinking_cache_enabled": True,
            "async_processing": True
        }
        
        # 模拟会话池
        self.active_sessions = {}
        self.session_pool = []
        self.tool_cache = {}
        
        print("🚀 性能优化测试器初始化完成")
    
    def measure_performance(self, operation_name: str, func):
        """性能测量方法"""
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            start_cpu = self.process.cpu_percent()
            
            success = True
            error_message = None
            result = None
            
            try:
                result = func(self, *args, **kwargs)
            except Exception as e:
                success = False
                error_message = str(e)
            
            end_time = time.time()
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            end_cpu = self.process.cpu_percent()
            
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                memory_usage=end_memory - start_memory,
                cpu_usage=max(start_cpu, end_cpu),
                success=success,
                error_message=error_message
            )
            
            self.metrics.append(metrics)
            return result
        return wrapper
    
    def create_session(self, session_type: SessionType, config: Dict[str, Any]) -> str:
        """创建会话（优化版本）"""
        session_id = f"{session_type.value}_{int(time.time() * 1000)}"
        
        # 会话池优化：重用已销毁的会话对象
        if self.session_pool:
            session_obj = self.session_pool.pop()
            session_obj.reset(session_id, session_type, config)
        else:
            session_obj = self._create_new_session(session_id, session_type, config)
        
        self.active_sessions[session_id] = session_obj
        
        # 记录会话指标
        session_metrics = SessionMetrics(
            session_id=session_id,
            session_type=session_type,
            creation_time=time.time(),
            destruction_time=None,
            total_tools_called=0,
            memory_peak=self.process.memory_info().rss / 1024 / 1024,
            cpu_peak=self.process.cpu_percent()
        )
        self.session_metrics.append(session_metrics)
        
        return session_id
    
    def _create_new_session(self, session_id: str, session_type: SessionType, config: Dict[str, Any]):
        """创建新会话对象"""
        return {
            "id": session_id,
            "type": session_type,
            "config": config,
            "created_at": time.time(),
            "tools_called": 0,
            "cache": {}
        }
    
    def destroy_session(self, session_id: str):
        """销毁会话（优化版本）"""
        if session_id in self.active_sessions:
            session_obj = self.active_sessions.pop(session_id)
            
            # 会话池优化：回收会话对象供重用
            if len(self.session_pool) < self.config["max_sessions"]:
                session_obj["cache"].clear()  # 清理缓存
                self.session_pool.append(session_obj)
            
            # 更新会话指标
            for metrics in self.session_metrics:
                if metrics.session_id == session_id:
                    metrics.destruction_time = time.time()
                    metrics.total_tools_called = session_obj["tools_called"]
                    break
    
    def call_tool_cached(self, tool_name: str, params: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """缓存优化的工具调用"""
        # 生成缓存键
        cache_key = f"{tool_name}_{hash(json.dumps(params, sort_keys=True))}"
        
        # 检查缓存
        if cache_key in self.tool_cache:
            return {
                "result": self.tool_cache[cache_key],
                "cached": True,
                "execution_time": 0.001  # 缓存命中时间
            }
        
        # 模拟工具执行
        start_time = time.time()
        result = self._execute_tool(tool_name, params)
        execution_time = time.time() - start_time
        
        # 更新缓存
        if len(self.tool_cache) < self.config["tool_cache_size"]:
            self.tool_cache[cache_key] = result
        
        # 更新会话统计
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["tools_called"] += 1
        
        return {
            "result": result,
            "cached": False,
            "execution_time": execution_time
        }
    
    def _execute_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """模拟工具执行"""
        # 模拟不同工具的执行时间
        execution_times = {
            "sequentialthinking": 0.1,
            "data_processing": 0.05,
            "technical_analysis": 0.08,
            "risk_management": 0.03
        }
        
        time.sleep(execution_times.get(tool_name, 0.02))
        
        return {
            "tool": tool_name,
            "params": params,
            "result": f"执行结果_{tool_name}_{int(time.time() * 1000)}",
            "timestamp": time.time()
        }
    
    def execute_concurrent_tools(self, tool_calls: List[Dict[str, Any]], session_id: str) -> List[Dict[str, Any]]:
        """并发工具调用优化"""
        results = []
        
        if self.config["async_processing"] and len(tool_calls) > 1:
            # 使用线程池并发执行
            with ThreadPoolExecutor(max_workers=min(len(tool_calls), 4)) as executor:
                future_to_call = {
                    executor.submit(
                        self.call_tool_cached,
                        call["tool_name"],
                        call["params"],
                        session_id
                    ): call for call in tool_calls
                }
                
                for future in as_completed(future_to_call):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append({"error": str(e), "cached": False})
        else:
            # 串行执行
            for call in tool_calls:
                result = self.call_tool_cached(
                    call["tool_name"],
                    call["params"],
                    session_id
                )
                results.append(result)
        
        return results
    
    def optimize_memory_usage(self):
        """内存使用优化"""
        # 清理过期缓存
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session_obj in self.active_sessions.items():
            if current_time - session_obj["created_at"] > self.config["session_timeout"]:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.destroy_session(session_id)
        
        # 清理工具缓存（LRU策略）
        if len(self.tool_cache) > self.config["tool_cache_size"] * 0.8:
            # 简单的缓存清理：删除一半缓存
            cache_items = list(self.tool_cache.items())
            self.tool_cache = dict(cache_items[len(cache_items)//2:])
        
        return {
            "expired_sessions_cleaned": len(expired_sessions),
            "cache_size_after_cleanup": len(self.tool_cache),
            "active_sessions": len(self.active_sessions)
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        if not self.metrics:
            return {"message": "暂无性能数据"}
        
        # 按操作类型分组统计
        operation_stats = {}
        for metric in self.metrics:
            op_name = metric.operation_name
            if op_name not in operation_stats:
                operation_stats[op_name] = {
                    "count": 0,
                    "total_duration": 0,
                    "total_memory": 0,
                    "max_duration": 0,
                    "min_duration": float('inf'),
                    "success_rate": 0,
                    "errors": []
                }
            
            stats = operation_stats[op_name]
            stats["count"] += 1
            stats["total_duration"] += metric.duration
            stats["total_memory"] += metric.memory_usage
            stats["max_duration"] = max(stats["max_duration"], metric.duration)
            stats["min_duration"] = min(stats["min_duration"], metric.duration)
            
            if metric.success:
                stats["success_rate"] += 1
            else:
                stats["errors"].append(metric.error_message)
        
        # 计算平均值和成功率
        for op_name, stats in operation_stats.items():
            if stats["count"] > 0:
                stats["avg_duration"] = stats["total_duration"] / stats["count"]
                stats["avg_memory"] = stats["total_memory"] / stats["count"]
                stats["success_rate"] = stats["success_rate"] / stats["count"]
                if stats["min_duration"] == float('inf'):
                    stats["min_duration"] = 0
        
        # 会话统计
        session_stats = {
            "total_sessions_created": len(self.session_metrics),
            "active_sessions": len(self.active_sessions),
            "session_pool_size": len(self.session_pool),
            "cache_size": len(self.tool_cache)
        }
        
        return {
            "performance_summary": {
                "test_duration": time.time() - (self.metrics[0].start_time if self.metrics else time.time()),
                "total_operations": len(self.metrics),
                "operation_statistics": operation_stats,
                "session_statistics": session_stats,
                "current_memory_usage": self.process.memory_info().rss / 1024 / 1024,
                "current_cpu_usage": self.process.cpu_percent()
            }
        }

def test_session_management_performance():
    """测试会话管理性能"""
    print("\n🧪 测试1: 会话管理性能")
    
    tester = PerformanceOptimizationTester()
    
    # 包装性能测量的方法
    create_session_measured = tester.measure_performance("session_creation", tester.create_session.__func__)
    destroy_session_measured = tester.measure_performance("session_destruction", tester.destroy_session.__func__)
    
    # 批量创建会话
    session_ids = []
    for i in range(20):
        session_id = create_session_measured(
            SessionType.SUB_SESSION if i % 2 else SessionType.MAIN_SESSION,
            {"task_name": f"测试任务_{i}", "timeout": 60}
        )
        session_ids.append(session_id)
    
    # 批量销毁会话
    for session_id in session_ids[:10]:
        destroy_session_measured(session_id)
    
    # 再次创建会话（测试会话池重用）
    for i in range(5):
        session_id = create_session_measured(
            SessionType.SUB_SESSION,
            {"task_name": f"重用测试_{i}", "timeout": 60}
        )
        session_ids.append(session_id)
    
    print("✅ 会话管理性能测试完成")
    return tester

def test_tool_call_performance(tester):
    """测试工具调用性能"""
    print("\n🧪 测试2: 工具调用性能")
    
    session_id = tester.create_session(
        SessionType.MAIN_SESSION,
        {"task_name": "工具调用测试", "cache_enabled": True}
    )
    
    # 包装性能测量的方法
    call_tool_measured = tester.measure_performance("tool_call_cached", tester.call_tool_cached.__func__)
    
    # 测试缓存效果
    tool_calls = [
        {"tool_name": "sequentialthinking", "params": {"problem": "测试问题1"}},
        {"tool_name": "data_processing", "params": {"data": "测试数据"}},
        {"tool_name": "sequentialthinking", "params": {"problem": "测试问题1"}},  # 重复调用
        {"tool_name": "technical_analysis", "params": {"indicator": "RSI"}}
    ]
    
    # 串行调用
    for call in tool_calls:
        result = call_tool_measured(call["tool_name"], call["params"], session_id)
        cache_status = "缓存命中" if result["cached"] else "新计算"
        print(f"   {call['tool_name']}: {cache_status} ({result['execution_time']:.3f}s)")
    
    print("✅ 工具调用性能测试完成")
    return tester

def test_concurrent_processing_performance(tester):
    """测试并发处理性能"""
    print("\n🧪 测试3: 并发处理性能")
    
    session_id = tester.create_session(
        SessionType.MAIN_SESSION,
        {"task_name": "并发测试", "async_enabled": True}
    )
    
    # 包装性能测量的方法
    execute_concurrent_measured = tester.measure_performance("concurrent_tool_calls", tester.execute_concurrent_tools.__func__)
    
    # 准备并发工具调用
    concurrent_calls = [
        {"tool_name": "sequentialthinking", "params": {"problem": f"并发问题_{i}"}}
        for i in range(8)
    ]
    
    # 测试并发执行
    start_time = time.time()
    results = execute_concurrent_measured(concurrent_calls, session_id)
    concurrent_duration = time.time() - start_time
    
    # 测试串行执行（对比）
    tester.config["async_processing"] = False
    start_time = time.time()
    serial_results = execute_concurrent_measured(concurrent_calls, session_id)
    serial_duration = time.time() - start_time
    tester.config["async_processing"] = True
    
    speedup = serial_duration / concurrent_duration if concurrent_duration > 0 else 1
    print(f"   并发执行时间: {concurrent_duration:.3f}s")
    print(f"   串行执行时间: {serial_duration:.3f}s")
    print(f"   性能提升: {speedup:.2f}x")
    
    print("✅ 并发处理性能测试完成")
    return tester

def test_memory_optimization_performance(tester):
    """测试内存优化性能"""
    print("\n🧪 测试4: 内存优化性能")
    
    # 包装性能测量的方法
    optimize_memory_measured = tester.measure_performance("memory_optimization", tester.optimize_memory_usage.__func__)
    
    # 创建大量会话和缓存
    for i in range(50):
        session_id = tester.create_session(
            SessionType.SUB_SESSION,
            {"task_name": f"内存测试_{i}", "timeout": 1}  # 短超时
        )
        
        # 创建缓存项
        for j in range(5):
            tester.call_tool_cached(
                "data_processing",
                {"data": f"测试数据_{i}_{j}"},
                session_id
            )
    
    memory_before = tester.process.memory_info().rss / 1024 / 1024
    cache_size_before = len(tester.tool_cache)
    sessions_before = len(tester.active_sessions)
    
    # 等待会话过期
    time.sleep(2)
    
    # 执行内存优化
    optimization_result = optimize_memory_measured()
    
    memory_after = tester.process.memory_info().rss / 1024 / 1024
    cache_size_after = len(tester.tool_cache)
    sessions_after = len(tester.active_sessions)
    
    print(f"   优化前: {sessions_before}个会话, {cache_size_before}个缓存项, {memory_before:.1f}MB")
    print(f"   优化后: {sessions_after}个会话, {cache_size_after}个缓存项, {memory_after:.1f}MB")
    print(f"   清理结果: {optimization_result}")
    
    print("✅ 内存优化性能测试完成")
    return tester

def test_stress_testing(tester):
    """压力测试"""
    print("\n🧪 测试5: 系统压力测试")
    
    # 模拟高负载场景
    stress_duration = 10  # 10秒压力测试
    start_time = time.time()
    operation_count = 0
    
    while time.time() - start_time < stress_duration:
        # 随机操作
        import random
        operation = random.choice(["create_session", "call_tool", "destroy_session"])
        
        try:
            if operation == "create_session":
                session_id = tester.create_session(
                    random.choice([SessionType.MAIN_SESSION, SessionType.SUB_SESSION]),
                    {"task_name": f"压力测试_{operation_count}", "timeout": 30}
                )
            
            elif operation == "call_tool" and tester.active_sessions:
                session_id = random.choice(list(tester.active_sessions.keys()))
                tool_name = random.choice(["sequentialthinking", "data_processing", "technical_analysis"])
                tester.call_tool_cached(
                    tool_name,
                    {"param": f"压力测试_{operation_count}"},
                    session_id
                )
            
            elif operation == "destroy_session" and tester.active_sessions:
                session_id = random.choice(list(tester.active_sessions.keys()))
                tester.destroy_session(session_id)
            
            operation_count += 1
            
        except Exception as e:
            print(f"   压力测试错误: {e}")
    
    # 定期内存优化
    tester.optimize_memory_usage()
    
    print(f"   压力测试完成: {operation_count}次操作 in {stress_duration}s")
    print(f"   平均操作速率: {operation_count/stress_duration:.1f} ops/s")
    
    print("✅ 系统压力测试完成")
    return tester

def test_performance_monitoring(tester):
    """测试性能监控"""
    print("\n🧪 测试6: 性能监控和报告")
    
    # 获取性能摘要
    summary = tester.get_performance_summary()
    
    print("\n📊 性能测试摘要:")
    perf_summary = summary["performance_summary"]
    
    print(f"   测试总时长: {perf_summary['test_duration']:.2f}s")
    print(f"   总操作数: {perf_summary['total_operations']}")
    print(f"   当前内存使用: {perf_summary['current_memory_usage']:.1f}MB")
    print(f"   当前CPU使用: {perf_summary['current_cpu_usage']:.1f}%")
    
    print("\n📈 操作性能统计:")
    for op_name, stats in perf_summary["operation_statistics"].items():
        print(f"   {op_name}:")
        print(f"     调用次数: {stats['count']}")
        print(f"     平均耗时: {stats['avg_duration']:.4f}s")
        print(f"     最大耗时: {stats['max_duration']:.4f}s")
        print(f"     最小耗时: {stats['min_duration']:.4f}s")
        print(f"     成功率: {stats['success_rate']:.2%}")
        if stats['errors']:
            print(f"     错误: {len(stats['errors'])}个")
    
    print("\n🔧 会话统计:")
    session_stats = perf_summary["session_statistics"]
    for key, value in session_stats.items():
        print(f"   {key}: {value}")
    
    print("✅ 性能监控测试完成")
    
    return summary

def main():
    """主测试函数"""
    print("🚀 AIOrchestrator V2.1 性能优化测试开始")
    print("=" * 60)
    
    try:
        # 执行所有性能测试
        tester = test_session_management_performance()
        tester = test_tool_call_performance(tester)
        tester = test_concurrent_processing_performance(tester)
        tester = test_memory_optimization_performance(tester)
        tester = test_stress_testing(tester)
        summary = test_performance_monitoring(tester)
        
        print("\n" + "=" * 60)
        print("🎉 所有性能优化测试完成!")
        
        # 性能优化建议
        print("\n💡 性能优化建议:")
        perf_data = summary["performance_summary"]
        
        # 分析会话管理性能
        session_ops = perf_data["operation_statistics"].get("session_creation", {})
        if session_ops.get("avg_duration", 0) > 0.01:
            print("   ⚠️  会话创建耗时较长，建议优化会话池管理")
        else:
            print("   ✅ 会话管理性能良好")
        
        # 分析工具调用性能
        tool_ops = perf_data["operation_statistics"].get("tool_call_cached", {})
        if tool_ops.get("avg_duration", 0) > 0.05:
            print("   ⚠️  工具调用耗时较长，建议增加缓存大小")
        else:
            print("   ✅ 工具调用性能良好")
        
        # 分析内存使用
        if perf_data["current_memory_usage"] > 500:  # 500MB
            print("   ⚠️  内存使用较高，建议增加清理频率")
        else:
            print("   ✅ 内存使用合理")
        
        # 分析并发性能
        concurrent_ops = perf_data["operation_statistics"].get("concurrent_tool_calls", {})
        if concurrent_ops.get("count", 0) > 0:
            print("   ✅ 并发处理功能正常")
        
        print("\n🔧 优化配置建议:")
        print("   - 会话池大小: 10-20")
        print("   - 工具缓存大小: 100-200")
        print("   - 并发线程数: 4-8")
        print("   - 会话超时: 300-600秒")
        print("   - 内存清理间隔: 60-120秒")
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()