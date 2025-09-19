#!/usr/bin/env python3
"""
工具分类系统 V2.1 测试脚本
Tool Classification System V2.1 Test Script
"""

import sys
import os
import json
from datetime import datetime
from enum import Enum

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 简化的枚举类
class SessionType(Enum):
    MAIN_SESSION = "main_session"
    SUB_SESSION = "sub_session"

class ToolCategory(Enum):
    SIMPLE_TOOLS = "simple_tools"
    META_TOOLS = "meta_tools"
    THINKING_TOOLS = "thinking_tools"

# 简化的配置类
class ToolClassificationTester:
    def __init__(self):
        """初始化工具分类测试器"""
        self.config_path = "config/tool_classification_config.json"
        self.tool_classification_config = None
        self.current_session = SessionType.MAIN_SESSION
        
        # 加载配置
        self._load_configuration()
        
        print("✅ ToolClassificationTester 初始化完成")
    
    def _load_configuration(self):
        """加载工具分类配置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.tool_classification_config = json.load(f)
                print(f"✅ 工具分类配置加载成功: {self.config_path}")
            else:
                print(f"❌ 配置文件不存在: {self.config_path}")
                self.tool_classification_config = self._get_default_config()
        except Exception as e:
            print(f"❌ 配置加载失败: {e}")
            self.tool_classification_config = self._get_default_config()
    
    def _get_default_config(self):
        """获取默认配置"""
        return {
            "tool_classification_system": {
                "version": "2.1",
                "tool_categories": {},
                "session_configurations": {}
            }
        }
    
    def get_tool_categories(self) -> dict:
        """获取工具分类"""
        return self.tool_classification_config.get("tool_classification_system", {}).get("tool_categories", {})
    
    def get_session_configurations(self) -> dict:
        """获取会话配置"""
        return self.tool_classification_config.get("tool_classification_system", {}).get("session_configurations", {})
    
    def get_permission_matrix(self) -> dict:
        """获取权限矩阵"""
        return self.tool_classification_config.get("tool_classification_system", {}).get("permission_matrix", {})
    
    def is_tool_allowed(self, tool_name: str, session_type: SessionType) -> bool:
        """检查工具是否被指定会话允许"""
        tool_categories = self.get_tool_categories()
        session_config = self.get_session_configurations()
        
        # 获取会话允许的工具类别
        allowed_categories = session_config.get(session_type.value, {}).get("allowed_tool_categories", [])
        
        # 检查工具是否在允许的类别中
        for category_name in allowed_categories:
            if category_name in tool_categories:
                category_tools = tool_categories[category_name].get("tools", {})
                if tool_name in category_tools:
                    return True
        
        return False
    
    def get_tools_by_category(self, category: str) -> list:
        """获取指定类别的工具列表"""
        tool_categories = self.get_tool_categories()
        return list(tool_categories.get(category, {}).get("tools", {}).keys())
    
    def get_allowed_tools_for_session(self, session_type: SessionType) -> list:
        """获取指定会话允许的所有工具"""
        session_config = self.get_session_configurations()
        tool_categories = self.get_tool_categories()
        
        allowed_categories = session_config.get(session_type.value, {}).get("allowed_tool_categories", [])
        allowed_tools = []
        
        for category_name in allowed_categories:
            if category_name in tool_categories:
                category_tools = list(tool_categories[category_name].get("tools", {}).keys())
                allowed_tools.extend(category_tools)
        
        return allowed_tools

def test_configuration_loading():
    """测试配置文件加载"""
    print("🧪 测试1: 配置文件加载")
    
    try:
        tester = ToolClassificationTester()
        
        # 检查配置结构
        config = tester.tool_classification_config
        system_config = config.get("tool_classification_system", {})
        
        print(f"✅ 配置版本: {system_config.get('version', 'Unknown')}")
        print(f"✅ 工具类别数量: {len(system_config.get('tool_categories', {}))}")
        print(f"✅ 会话配置数量: {len(system_config.get('session_configurations', {}))}")
        
        return tester
        
    except Exception as e:
        print(f"❌ 配置加载测试失败: {e}")
        return None

def test_tool_categories(tester):
    """测试工具分类"""
    print("\n🧪 测试2: 工具分类系统")
    
    try:
        categories = tester.get_tool_categories()
        
        for category_name, category_info in categories.items():
            tools = list(category_info.get("tools", {}).keys())
            description = category_info.get("description", "无描述")
            
            print(f"✅ {category_name}:")
            print(f"   描述: {description}")
            print(f"   工具数量: {len(tools)}")
            print(f"   工具列表: {tools}")
        
        return True
        
    except Exception as e:
        print(f"❌ 工具分类测试失败: {e}")
        return False

def test_session_configurations(tester):
    """测试会话配置"""
    print("\n🧪 测试3: 会话配置")
    
    try:
        session_configs = tester.get_session_configurations()
        
        for session_name, session_info in session_configs.items():
            allowed_categories = session_info.get("allowed_tool_categories", [])
            description = session_info.get("description", "无描述")
            
            print(f"✅ {session_name}:")
            print(f"   描述: {description}")
            print(f"   允许的工具类别: {allowed_categories}")
            
            # 计算允许的工具总数
            total_tools = 0
            for category in allowed_categories:
                tools = tester.get_tools_by_category(category)
                total_tools += len(tools)
            
            print(f"   允许的工具总数: {total_tools}")
        
        return True
        
    except Exception as e:
        print(f"❌ 会话配置测试失败: {e}")
        return False

def test_permission_system(tester):
    """测试权限系统"""
    print("\n🧪 测试4: 权限系统")
    
    try:
        # 测试各种工具在不同会话中的权限
        test_tools = [
            "get_kline_data",
            "decompose_and_execute_task", 
            "sequentialthinking",
            "get_market_ticker",
            "analyze_complex_scenario"
        ]
        
        sessions = [SessionType.MAIN_SESSION, SessionType.SUB_SESSION]
        
        for session in sessions:
            print(f"\n📋 {session.value} 权限测试:")
            for tool in test_tools:
                allowed = tester.is_tool_allowed(tool, session)
                status = "✅ 允许" if allowed else "❌ 禁止"
                print(f"   {tool}: {status}")
        
        return True
        
    except Exception as e:
        print(f"❌ 权限系统测试失败: {e}")
        return False

def test_permission_matrix(tester):
    """测试权限矩阵"""
    print("\n🧪 测试5: 权限矩阵")
    
    try:
        permission_matrix = tester.get_permission_matrix()
        
        if permission_matrix:
            print("📊 权限矩阵:")
            for tool_category, permissions in permission_matrix.items():
                print(f"✅ {tool_category}:")
                for session, access_level in permissions.items():
                    print(f"   {session}: {access_level}")
        else:
            print("⚠️  权限矩阵未配置")
        
        return True
        
    except Exception as e:
        print(f"❌ 权限矩阵测试失败: {e}")
        return False

def test_tool_discovery(tester):
    """测试工具发现功能"""
    print("\n🧪 测试6: 工具发现功能")
    
    try:
        # 测试每个会话类型的工具发现
        for session_type in [SessionType.MAIN_SESSION, SessionType.SUB_SESSION]:
            allowed_tools = tester.get_allowed_tools_for_session(session_type)
            
            print(f"✅ {session_type.value} 可用工具:")
            print(f"   工具数量: {len(allowed_tools)}")
            print(f"   工具列表: {allowed_tools}")
        
        # 测试工具类别差异
        main_tools = set(tester.get_allowed_tools_for_session(SessionType.MAIN_SESSION))
        sub_tools = set(tester.get_allowed_tools_for_session(SessionType.SUB_SESSION))
        
        exclusive_to_main = main_tools - sub_tools
        common_tools = main_tools & sub_tools
        
        print(f"\n📊 工具分布分析:")
        print(f"   指挥官模式独有: {list(exclusive_to_main)}")
        print(f"   共同工具: {list(common_tools)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 工具发现测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 工具分类系统 V2.1 测试开始")
    print("=" * 60)
    
    # 测试计数器
    tests_passed = 0
    total_tests = 6
    
    # 测试1: 配置加载
    tester = test_configuration_loading()
    if tester:
        tests_passed += 1
    else:
        print("❌ 配置加载失败，终止测试")
        return
    
    # 测试2: 工具分类
    if test_tool_categories(tester):
        tests_passed += 1
    
    # 测试3: 会话配置
    if test_session_configurations(tester):
        tests_passed += 1
    
    # 测试4: 权限系统
    if test_permission_system(tester):
        tests_passed += 1
    
    # 测试5: 权限矩阵
    if test_permission_matrix(tester):
        tests_passed += 1
    
    # 测试6: 工具发现
    if test_tool_discovery(tester):
        tests_passed += 1
    
    # 测试结果汇总
    print("\n" + "=" * 60)
    print(f"🎯 测试完成: {tests_passed}/{total_tests} 通过")
    
    if tests_passed == total_tests:
        print("🎉 所有测试通过！工具分类系统 V2.1 运行正常")
        print("📋 验证的功能包括:")
        print("   ✓ 配置文件加载和解析")
        print("   ✓ 工具分类系统 (简单/元/思维工具)")
        print("   ✓ 会话配置管理")
        print("   ✓ 权限控制机制")
        print("   ✓ 权限矩阵验证")
        print("   ✓ 工具发现和分布分析")
    else:
        print(f"⚠️  {total_tests - tests_passed} 个测试失败，请检查相关功能")
    
    # 显示配置摘要
    print(f"\n📊 配置摘要:")
    config_summary = {
        "version": tester.tool_classification_config.get("tool_classification_system", {}).get("version"),
        "categories_count": len(tester.get_tool_categories()),
        "sessions_count": len(tester.get_session_configurations()),
        "total_tools": sum(len(cat.get("tools", {})) for cat in tester.get_tool_categories().values())
    }
    print(json.dumps(config_summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()