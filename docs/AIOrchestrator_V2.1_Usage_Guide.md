# AIOrchestrator V2.1 使用指南

## 概述

AIOrchestrator V2.1 是一个先进的AI编排系统，支持"指挥官-执行官"模式的递归调用和深度思考集成。本指南将帮助您了解如何有效使用这个强大的系统。

## 核心特性

### 1. 工具分类系统
- **Simple Tools**: 基础工具，如文件操作、数据处理
- **Meta Tools**: 元工具，如会话管理、编排控制
- **Thinking Tools**: 思考工具，如sequentialthinking、分析工具

### 2. 会话类型管理
- **Main Session**: 主会话，拥有完整权限
- **Sub Session**: 子会话，权限受限，专注特定任务

### 3. 递归编排能力
- 支持多层会话嵌套（最大深度3层）
- 自动会话清理和资源管理
- 会话间通信机制

### 4. 深度思考集成
- 集成sequentialthinking进行结构化思考
- "思考-行动"循环模式
- 智能洞察生成和结果综合

## 快速开始

### 基本使用

```python
from src.ai_orchestrator import AIOrchestrator, SessionType

# 创建编排器实例
orchestrator = AIOrchestrator()

# 配置主会话
config = {
    "session_type": SessionType.MAIN_SESSION,
    "max_depth": 3,
    "thinking_enabled": True
}

orchestrator.configure_session(config)

# 执行任务
result = orchestrator.execute_task({
    "task_type": "data_analysis",
    "data_source": "market_data.csv",
    "analysis_depth": "deep"
})
```

### 子会话创建

```python
# 在主会话中创建子会话
sub_session_config = {
    "session_type": SessionType.SUB_SESSION,
    "parent_session": "main_001",
    "task_focus": "technical_analysis",
    "allowed_tools": ["sequentialthinking", "data_processing"]
}

sub_result = orchestrator.create_sub_session(sub_session_config)
```

### 思考集成使用

```python
# 启用深度思考模式
thinking_config = {
    "thinking_mode": "sequential",
    "max_steps": 10,
    "action_integration": True,
    "insight_generation": True
}

thinking_result = orchestrator.execute_thinking_task(
    problem="复杂市场趋势分析",
    config=thinking_config
)
```

## 配置文件说明

### 主配置文件 (enhanced_config.yaml)

```yaml
orchestrator:
  version: "V2.1"
  max_session_depth: 3
  session_timeout: 300
  thinking_integration: true
  
session_management:
  auto_cleanup: true
  resource_monitoring: true
  communication_enabled: true
  
logging:
  level: "INFO"
  file: "logs/orchestrator.log"
  format: "detailed"
```

### 工具分类配置 (tool_classification_config.json)

```json
{
  "version": "2.1",
  "description": "AIOrchestrator V2.1 工具分类系统",
  "tool_categories": {
    "simple_tools": {
      "description": "基础工具集合",
      "tools": ["file_operations", "data_processing", "basic_analysis"]
    },
    "meta_tools": {
      "description": "元工具和编排工具",
      "tools": ["session_management", "orchestration", "workflow_control"]
    },
    "thinking_tools": {
      "description": "思考和分析工具",
      "tools": ["sequentialthinking", "deep_analysis", "pattern_recognition"]
    }
  },
  "session_configurations": {
    "main_session": {
      "allowed_categories": ["simple_tools", "meta_tools", "thinking_tools"]
    },
    "sub_session": {
      "allowed_categories": ["simple_tools", "thinking_tools"]
    }
  }
}
```

## 最佳实践

### 1. 会话设计原则

#### 主会话职责
- 整体任务规划和协调
- 子会话创建和管理
- 结果整合和决策制定
- 资源分配和监控

#### 子会话职责
- 专注特定子任务
- 深度分析和思考
- 详细执行和报告
- 与父会话通信

### 2. 工具选择策略

```python
# 根据任务复杂度选择合适的工具
def select_tools_by_complexity(task_complexity):
    if task_complexity == "simple":
        return ["file_operations", "basic_analysis"]
    elif task_complexity == "medium":
        return ["data_processing", "pattern_recognition"]
    elif task_complexity == "complex":
        return ["sequentialthinking", "deep_analysis", "orchestration"]
    else:
        return ["all_tools"]  # 最高权限
```

### 3. 思考模式优化

```python
# 针对不同问题类型的思考配置
thinking_configs = {
    "analytical": {
        "max_steps": 15,
        "focus": "data_analysis",
        "action_ratio": 0.6
    },
    "creative": {
        "max_steps": 20,
        "focus": "pattern_discovery",
        "action_ratio": 0.4
    },
    "strategic": {
        "max_steps": 25,
        "focus": "decision_making",
        "action_ratio": 0.8
    }
}
```

### 4. 错误处理和恢复

```python
# 实现健壮的错误处理
try:
    result = orchestrator.execute_complex_task(task_config)
except SessionDepthExceeded:
    # 会话深度超限处理
    result = orchestrator.execute_simplified_task(task_config)
except ThinkingTimeout:
    # 思考超时处理
    result = orchestrator.get_partial_results()
except ResourceExhausted:
    # 资源耗尽处理
    orchestrator.cleanup_sessions()
    result = orchestrator.retry_with_reduced_scope(task_config)
```

## 性能优化建议

### 1. 会话管理优化
- 及时清理完成的子会话
- 合理设置会话超时时间
- 监控会话资源使用情况

### 2. 思考过程优化
- 根据问题复杂度调整思考步数
- 平衡思考和行动的比例
- 使用缓存机制避免重复思考

### 3. 工具调用优化
- 预加载常用工具
- 批量处理相似任务
- 实现工具调用池化

## 监控和调试

### 日志配置

```python
# 启用详细日志记录
logging_config = {
    "level": "DEBUG",
    "handlers": {
        "file": "logs/orchestrator_debug.log",
        "console": True
    },
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}
```

### 性能监控

```python
# 监控关键指标
metrics = orchestrator.get_performance_metrics()
print(f"会话数量: {metrics['active_sessions']}")
print(f"平均响应时间: {metrics['avg_response_time']}ms")
print(f"思考步骤总数: {metrics['total_thinking_steps']}")
print(f"成功率: {metrics['success_rate']:.2%}")
```

## 故障排除

### 常见问题

1. **会话创建失败**
   - 检查配置文件是否正确
   - 验证权限设置
   - 确认资源可用性

2. **思考过程卡住**
   - 调整思考步数限制
   - 检查输入数据质量
   - 重启思考会话

3. **工具调用权限错误**
   - 验证工具分类配置
   - 检查会话类型设置
   - 更新权限矩阵

### 调试技巧

```python
# 启用调试模式
orchestrator.enable_debug_mode()

# 获取详细状态信息
status = orchestrator.get_detailed_status()
print(json.dumps(status, indent=2, ensure_ascii=False))

# 单步执行思考过程
for step in orchestrator.debug_thinking_process(problem):
    print(f"步骤 {step['number']}: {step['thought']}")
    input("按回车继续...")
```

## 扩展开发

### 自定义工具集成

```python
# 注册自定义工具
@orchestrator.register_tool("custom_analysis")
def custom_analysis_tool(data, config):
    # 自定义分析逻辑
    result = perform_custom_analysis(data, config)
    return {
        "status": "success",
        "result": result,
        "metadata": {"tool": "custom_analysis"}
    }
```

### 自定义思考模式

```python
# 实现自定义思考适配器
class CustomThinkingAdapter:
    def __init__(self, config):
        self.config = config
    
    def execute_thinking_cycle(self, problem, context):
        # 自定义思考逻辑
        steps = self.generate_thinking_steps(problem)
        results = self.execute_steps(steps, context)
        return self.synthesize_results(results)

# 注册自定义适配器
orchestrator.register_thinking_adapter("custom", CustomThinkingAdapter)
```

## 版本更新说明

### V2.1 新特性
- 增强的工具分类系统
- 深度思考集成
- 递归会话管理
- 改进的权限控制
- 性能优化

### 迁移指南
从V2.0升级到V2.1时，请注意：
1. 更新配置文件格式
2. 调整工具权限设置
3. 测试思考集成功能
4. 验证会话管理逻辑

## 支持和社区

- 文档更新：定期查看最新文档
- 问题反馈：通过GitHub Issues报告问题
- 功能建议：参与社区讨论
- 技术支持：联系开发团队

---

*本文档持续更新中，最后更新时间：2025年1月*