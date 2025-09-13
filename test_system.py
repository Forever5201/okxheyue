"""
系统测试脚本
System Test Script
"""

import os
from dotenv import load_dotenv

def test_imports():
    """测试导入"""
    try:
        print("🧪 测试导入...")
        
        from src.logger import setup_logger
        print("✅ logger - OK")
        
        from okx.api import Account, Market, Public
        print("✅ OKX API - OK")
        
        import pandas as pd
        import ta
        print("✅ pandas, ta - OK")
        
        from src.config_loader import ConfigLoader
        print("✅ config_loader - OK")
        
        return True
        
    except Exception as e:
        print(f"❌ 导入错误: {e}")
        return False

def test_config():
    """测试配置"""
    try:
        print("\n📋 测试配置...")
        
        load_dotenv()
        
        required_vars = ['OKX_API_KEY', 'OKX_API_SECRET', 'OKX_API_PASSPHRASE', 'MCP_API_KEY']
        for var in required_vars:
            value = os.getenv(var)
            if value:
                print(f"✅ {var} - 已设置")
            else:
                print(f"❌ {var} - 未设置")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ 配置错误: {e}")
        return False

def test_okx_connection():
    """测试OKX连接"""
    try:
        print("\n🔗 测试OKX连接...")
        
        from okx.api import Market
        
        # 创建市场API客户端（不需要认证）
        market_api = Market()
        
        # 测试获取BTC价格
        result = market_api.tickers(instType="SWAP", instId="BTC-USD-SWAP")
        
        if result and result.get('data'):
            price_data = result['data'][0]
            print(f"✅ OKX连接成功 - BTC价格: ${price_data.get('last', 'N/A')}")
            return True
        else:
            print("❌ 无法获取价格数据")
            return False
            
    except Exception as e:
        print(f"❌ OKX连接错误: {e}")
        return False

def test_mcp_service():
    """测试MCP服务"""
    try:
        print("\n🌐 测试MCP服务...")
        
        from src.mcp_service import app
        print("✅ MCP服务导入成功")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP服务错误: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 AI交易系统 - 系统测试")
    print("=" * 60)
    
    tests = [
        ("导入测试", test_imports),
        ("配置测试", test_config),
        ("OKX连接测试", test_okx_connection),
        ("MCP服务测试", test_mcp_service)
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        if test_func():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统准备就绪")
    else:
        print("⚠️  部分测试失败，请检查配置")
    
    print("=" * 60)

if __name__ == "__main__":
    main()