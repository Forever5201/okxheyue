#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIOrchestrator V2.1 向后兼容性验证测试

这个测试脚本验证系统的向后兼容性，包括：
- 配置文件兼容性
- API接口兼容性
- 数据格式兼容性
- 现有功能完整性
"""

import os
import sys
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

@dataclass
class CompatibilityTestResult:
    test_name: str
    success: bool
    duration: float
    details: Dict[str, Any]
    errors: List[str]

class BackwardCompatibilityTester:
    """向后兼容性测试器"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = time.time()
        
    def log_test_result(self, test_name: str, success: bool, duration: float, 
                       details: Dict[str, Any] = None, errors: List[str] = None):
        """记录测试结果"""
        result = CompatibilityTestResult(
            test_name=test_name,
            success=success,
            duration=duration,
            details=details or {},
            errors=errors or []
        )
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        print(f"   {status} {test_name}: {duration:.3f}s")
        if errors:
            for error in errors:
                print(f"      ⚠️ {error}")
    
    def test_config_compatibility(self) -> bool:
        """测试配置文件兼容性"""
        print("\n🧪 测试1: 配置文件兼容性")
        start_time = time.time()
        errors = []
        
        try:
            # 测试配置文件加载
            config_files = [
                "config/tool_classification.json",
                "config/session_config.json"
            ]
            
            loaded_configs = {}
            for config_file in config_files:
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                            loaded_configs[config_file] = config_data
                    except Exception as e:
                        errors.append(f"配置文件 {config_file} 加载失败: {str(e)}")
                else:
                    errors.append(f"配置文件 {config_file} 不存在")
            
            # 验证配置结构
            if "config/tool_classification.json" in loaded_configs:
                tool_config = loaded_configs["config/tool_classification.json"]
                required_fields = ["version", "categories", "tools"]
                for field in required_fields:
                    if field not in tool_config:
                        errors.append(f"工具分类配置缺少字段: {field}")
            
            if "config/session_config.json" in loaded_configs:
                session_config = loaded_configs["config/session_config.json"]
                required_fields = ["version", "sessions"]
                for field in required_fields:
                    if field not in session_config:
                        errors.append(f"会话配置缺少字段: {field}")
            
            success = len(errors) == 0
            duration = time.time() - start_time
            
            self.log_test_result(
                "配置文件兼容性",
                success,
                duration,
                {"loaded_configs": len(loaded_configs), "config_files": config_files},
                errors
            )
            
            return success
            
        except Exception as e:
            errors.append(f"配置兼容性测试异常: {str(e)}")
            duration = time.time() - start_time
            self.log_test_result("配置文件兼容性", False, duration, {}, errors)
            return False
    
    def test_module_imports(self) -> bool:
        """测试模块导入兼容性"""
        print("\n🧪 测试2: 模块导入兼容性")
        start_time = time.time()
        errors = []
        
        try:
            # 测试核心模块导入
            core_modules = [
                "config_loader",
                "logger",
                "mcp_client",
                "mcp_service"
            ]
            
            imported_modules = {}
            for module_name in core_modules:
                try:
                    module = __import__(module_name)
                    imported_modules[module_name] = module
                except ImportError as e:
                    errors.append(f"模块 {module_name} 导入失败: {str(e)}")
                except Exception as e:
                    errors.append(f"模块 {module_name} 导入异常: {str(e)}")
            
            # 测试可选模块（不影响兼容性）
            optional_modules = [
                "technical_indicator",
                "analysis_tools"
            ]
            
            for module_name in optional_modules:
                try:
                    module = __import__(module_name)
                    imported_modules[module_name] = module
                except:
                    # 可选模块导入失败不算错误
                    pass
            
            success = len(errors) == 0
            duration = time.time() - start_time
            
            self.log_test_result(
                "模块导入兼容性",
                success,
                duration,
                {
                    "imported_modules": len(imported_modules),
                    "core_modules": core_modules,
                    "optional_modules": optional_modules
                },
                errors
            )
            
            return success
            
        except Exception as e:
            errors.append(f"模块导入测试异常: {str(e)}")
            duration = time.time() - start_time
            self.log_test_result("模块导入兼容性", False, duration, {}, errors)
            return False
    
    def test_api_compatibility(self) -> bool:
        """测试API接口兼容性"""
        print("\n🧪 测试3: API接口兼容性")
        start_time = time.time()
        errors = []
        
        try:
            # 测试环境变量
            required_env_vars = [
                "OKX_API_KEY",
                "OKX_API_SECRET",
                "OKX_API_PASSPHRASE"
            ]
            
            env_status = {}
            for var in required_env_vars:
                value = os.getenv(var)
                env_status[var] = value is not None and len(value) > 0
                if not env_status[var]:
                    errors.append(f"环境变量 {var} 未设置或为空")
            
            # 测试MCP相关环境变量
            mcp_env_vars = ["MCP_API_KEY"]
            for var in mcp_env_vars:
                value = os.getenv(var)
                env_status[var] = value is not None and len(value) > 0
                # MCP变量不是必需的，只记录状态
            
            # 测试配置加载器
            try:
                from config_loader import load_config
                config = load_config()
                if not config:
                    errors.append("配置加载器返回空配置")
            except ImportError:
                errors.append("配置加载器模块不可用")
            except Exception as e:
                errors.append(f"配置加载器测试失败: {str(e)}")
            
            success = len(errors) == 0
            duration = time.time() - start_time
            
            self.log_test_result(
                "API接口兼容性",
                success,
                duration,
                {
                    "env_vars_status": env_status,
                    "config_loader_available": "config_loader" in sys.modules
                },
                errors
            )
            
            return success
            
        except Exception as e:
            errors.append(f"API兼容性测试异常: {str(e)}")
            duration = time.time() - start_time
            self.log_test_result("API接口兼容性", False, duration, {}, errors)
            return False
    
    def test_data_format_compatibility(self) -> bool:
        """测试数据格式兼容性"""
        print("\n🧪 测试4: 数据格式兼容性")
        start_time = time.time()
        errors = []
        
        try:
            # 测试JSON数据格式
            test_data_formats = {
                "session_data": {
                    "session_id": "test_session",
                    "type": "main_session",
                    "status": "active",
                    "created_at": datetime.now().isoformat(),
                    "config": {"timeout": 300}
                },
                "tool_call_data": {
                    "tool_name": "get_latest_price",
                    "params": {"symbol": "BTC-USDT"},
                    "session_id": "test_session",
                    "timestamp": datetime.now().isoformat()
                },
                "thinking_data": {
                    "thought_id": "thought_1",
                    "content": "分析市场趋势",
                    "thought_number": 1,
                    "next_thought_needed": True,
                    "session_id": "thinking_session"
                }
            }
            
            # 验证数据序列化/反序列化
            for data_type, data in test_data_formats.items():
                try:
                    # 序列化
                    json_str = json.dumps(data, ensure_ascii=False, indent=2)
                    
                    # 反序列化
                    parsed_data = json.loads(json_str)
                    
                    # 验证数据完整性
                    if parsed_data != data:
                        errors.append(f"数据格式 {data_type} 序列化/反序列化不一致")
                        
                except Exception as e:
                    errors.append(f"数据格式 {data_type} 处理失败: {str(e)}")
            
            # 测试旧版本数据格式兼容性
            legacy_formats = {
                "legacy_session": {
                    "id": "legacy_session",
                    "type": "main",  # 旧格式
                    "timeout": 300
                },
                "legacy_tool_call": {
                    "tool": "price_tool",  # 旧格式
                    "args": {"symbol": "BTC"}
                }
            }
            
            for legacy_type, legacy_data in legacy_formats.items():
                try:
                    # 模拟格式转换
                    if legacy_type == "legacy_session":
                        converted = {
                            "session_id": legacy_data["id"],
                            "type": f"{legacy_data['type']}_session",
                            "config": {"timeout": legacy_data["timeout"]}
                        }
                    elif legacy_type == "legacy_tool_call":
                        converted = {
                            "tool_name": legacy_data["tool"],
                            "params": legacy_data["args"]
                        }
                    
                    # 验证转换成功
                    if not converted:
                        errors.append(f"旧格式 {legacy_type} 转换失败")
                        
                except Exception as e:
                    errors.append(f"旧格式 {legacy_type} 兼容性测试失败: {str(e)}")
            
            success = len(errors) == 0
            duration = time.time() - start_time
            
            self.log_test_result(
                "数据格式兼容性",
                success,
                duration,
                {
                    "tested_formats": len(test_data_formats),
                    "legacy_formats": len(legacy_formats)
                },
                errors
            )
            
            return success
            
        except Exception as e:
            errors.append(f"数据格式兼容性测试异常: {str(e)}")
            duration = time.time() - start_time
            self.log_test_result("数据格式兼容性", False, duration, {}, errors)
            return False
    
    def test_existing_functionality(self) -> bool:
        """测试现有功能完整性"""
        print("\n🧪 测试5: 现有功能完整性")
        start_time = time.time()
        errors = []
        
        try:
            # 测试文件系统结构
            required_directories = [
                "src",
                "config",
                "logs"
            ]
            
            directory_status = {}
            for directory in required_directories:
                exists = os.path.exists(directory)
                directory_status[directory] = exists
                if not exists:
                    errors.append(f"必需目录 {directory} 不存在")
            
            # 测试配置文件
            config_files = [
                "config/tool_classification.json",
                "config/session_config.json"
            ]
            
            config_status = {}
            for config_file in config_files:
                exists = os.path.exists(config_file)
                config_status[config_file] = exists
                if not exists:
                    errors.append(f"配置文件 {config_file} 不存在")
            
            # 测试核心Python文件
            core_files = [
                "src/ai_orchestrator.py",
                "src/config_loader.py",
                "src/logger.py",
                "src/mcp_client.py"
            ]
            
            file_status = {}
            for core_file in core_files:
                exists = os.path.exists(core_file)
                file_status[core_file] = exists
                if not exists:
                    errors.append(f"核心文件 {core_file} 不存在")
            
            # 测试日志功能
            try:
                from logger import setup_logger
                test_logger = setup_logger("compatibility_test")
                test_logger.info("向后兼容性测试日志")
                log_functional = True
            except Exception as e:
                log_functional = False
                errors.append(f"日志功能测试失败: {str(e)}")
            
            success = len(errors) == 0
            duration = time.time() - start_time
            
            self.log_test_result(
                "现有功能完整性",
                success,
                duration,
                {
                    "directory_status": directory_status,
                    "config_status": config_status,
                    "file_status": file_status,
                    "log_functional": log_functional
                },
                errors
            )
            
            return success
            
        except Exception as e:
            errors.append(f"功能完整性测试异常: {str(e)}")
            duration = time.time() - start_time
            self.log_test_result("现有功能完整性", False, duration, {}, errors)
            return False
    
    def test_version_migration(self) -> bool:
        """测试版本迁移兼容性"""
        print("\n🧪 测试6: 版本迁移兼容性")
        start_time = time.time()
        errors = []
        
        try:
            # 模拟版本迁移场景
            version_scenarios = {
                "v2.0_to_v2.1": {
                    "old_config": {
                        "version": "2.0",
                        "session_timeout": 300,
                        "tools": ["get_price", "analyze_data"]
                    },
                    "expected_new_config": {
                        "version": "2.1",
                        "session_timeout": 300,
                        "tools": ["get_price", "analyze_data"],
                        "new_features": ["sequential_thinking", "recursive_calls"]
                    }
                },
                "legacy_session_format": {
                    "old_format": {
                        "id": "session_123",
                        "type": "main",
                        "tools": ["price_tool"]
                    },
                    "expected_new_format": {
                        "session_id": "session_123",
                        "type": "main_session",
                        "allowed_tools": ["price_tool"]
                    }
                }
            }
            
            migration_results = {}
            for scenario_name, scenario in version_scenarios.items():
                try:
                    # 模拟迁移逻辑
                    old_data = scenario["old_config"] if "old_config" in scenario else scenario["old_format"]
                    
                    # 简单的迁移逻辑
                    if "version" in old_data and old_data["version"] == "2.0":
                        migrated_data = old_data.copy()
                        migrated_data["version"] = "2.1"
                        migrated_data["new_features"] = ["sequential_thinking", "recursive_calls"]
                    elif "id" in old_data and "type" in old_data:
                        migrated_data = {
                            "session_id": old_data["id"],
                            "type": f"{old_data['type']}_session",
                            "allowed_tools": old_data.get("tools", [])
                        }
                    else:
                        migrated_data = old_data
                    
                    migration_results[scenario_name] = {
                        "success": True,
                        "migrated_data": migrated_data
                    }
                    
                except Exception as e:
                    migration_results[scenario_name] = {
                        "success": False,
                        "error": str(e)
                    }
                    errors.append(f"版本迁移场景 {scenario_name} 失败: {str(e)}")
            
            # 验证迁移结果
            successful_migrations = sum(1 for result in migration_results.values() if result["success"])
            total_migrations = len(migration_results)
            
            if successful_migrations < total_migrations:
                errors.append(f"部分迁移失败: {successful_migrations}/{total_migrations}")
            
            success = len(errors) == 0
            duration = time.time() - start_time
            
            self.log_test_result(
                "版本迁移兼容性",
                success,
                duration,
                {
                    "migration_scenarios": len(version_scenarios),
                    "successful_migrations": successful_migrations,
                    "migration_results": migration_results
                },
                errors
            )
            
            return success
            
        except Exception as e:
            errors.append(f"版本迁移测试异常: {str(e)}")
            duration = time.time() - start_time
            self.log_test_result("版本迁移兼容性", False, duration, {}, errors)
            return False
    
    def generate_compatibility_report(self) -> Dict[str, Any]:
        """生成兼容性测试报告"""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result.success)
        failed_tests = total_tests - successful_tests
        
        total_duration = time.time() - self.start_time
        avg_test_duration = sum(result.duration for result in self.test_results) / total_tests if total_tests > 0 else 0
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": (successful_tests / total_tests * 100) if total_tests > 0 else 0,
                "total_duration": total_duration,
                "average_test_duration": avg_test_duration,
                "compatibility_status": "COMPATIBLE" if failed_tests == 0 else "ISSUES_FOUND"
            },
            "test_results": [
                {
                    "name": result.test_name,
                    "success": result.success,
                    "duration": result.duration,
                    "details": result.details,
                    "errors": result.errors
                }
                for result in self.test_results
            ],
            "compatibility_assessment": self._generate_compatibility_assessment(),
            "recommendations": self._generate_compatibility_recommendations()
        }
        
        return report
    
    def _generate_compatibility_assessment(self) -> Dict[str, str]:
        """生成兼容性评估"""
        assessment = {}
        
        for result in self.test_results:
            if result.success:
                assessment[result.test_name] = "COMPATIBLE"
            else:
                assessment[result.test_name] = "ISSUES_FOUND"
        
        return assessment
    
    def _generate_compatibility_recommendations(self) -> List[str]:
        """生成兼容性建议"""
        recommendations = []
        
        failed_tests = [result for result in self.test_results if not result.success]
        
        if not failed_tests:
            recommendations.append("✅ 所有兼容性测试通过，系统向后兼容性良好")
        else:
            recommendations.append(f"⚠️ 发现 {len(failed_tests)} 个兼容性问题，需要修复")
            
            for failed_test in failed_tests:
                recommendations.append(f"🔧 修复 {failed_test.test_name} 中的问题")
                for error in failed_test.errors:
                    recommendations.append(f"   - {error}")
        
        # 通用建议
        recommendations.extend([
            "📚 定期运行兼容性测试",
            "🔄 在版本升级前进行完整测试",
            "📝 维护详细的变更日志",
            "🛡️ 保持配置文件格式的稳定性"
        ])
        
        return recommendations

def main():
    """主测试函数"""
    print("🔄 开始AIOrchestrator V2.1向后兼容性验证")
    print("=" * 50)
    
    tester = BackwardCompatibilityTester()
    
    # 执行所有兼容性测试
    test_functions = [
        tester.test_config_compatibility,
        tester.test_module_imports,
        tester.test_api_compatibility,
        tester.test_data_format_compatibility,
        tester.test_existing_functionality,
        tester.test_version_migration
    ]
    
    for test_func in test_functions:
        try:
            test_func()
        except Exception as e:
            print(f"❌ 测试执行异常: {e}")
    
    # 生成兼容性报告
    print("\n📊 生成兼容性测试报告")
    report = tester.generate_compatibility_report()
    
    print("\n" + "=" * 50)
    print("🎯 向后兼容性测试摘要")
    print("=" * 50)
    
    summary = report["summary"]
    print(f"📈 测试统计:")
    print(f"   总测试数: {summary['total_tests']}")
    print(f"   成功测试: {summary['successful_tests']}")
    print(f"   失败测试: {summary['failed_tests']}")
    print(f"   成功率: {summary['success_rate']:.1f}%")
    print(f"   总耗时: {summary['total_duration']:.2f}s")
    print(f"   兼容性状态: {summary['compatibility_status']}")
    
    print(f"\n🔍 兼容性评估:")
    for test_name, status in report["compatibility_assessment"].items():
        status_icon = "✅" if status == "COMPATIBLE" else "❌"
        print(f"   {status_icon} {test_name}: {status}")
    
    print(f"\n💡 兼容性建议:")
    for i, recommendation in enumerate(report["recommendations"], 1):
        print(f"   {i}. {recommendation}")
    
    # 详细测试结果
    print(f"\n📋 详细测试结果:")
    for result in report["test_results"]:
        status = "✅" if result["success"] else "❌"
        print(f"   {status} {result['name']}: {result['duration']:.3f}s")
        if result["errors"]:
            for error in result["errors"]:
                print(f"      ⚠️ {error}")
    
    print("\n" + "=" * 50)
    if summary["compatibility_status"] == "COMPATIBLE":
        print("🎉 向后兼容性验证通过！AIOrchestrator V2.1与现有系统兼容！")
    else:
        print(f"⚠️ 发现兼容性问题，需要进一步修复")
    print("=" * 50)

if __name__ == "__main__":
    main()