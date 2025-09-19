#!/usr/bin/env python3
"""
测试MCP架构的完整数据流
验证AI工具调用是否能正确通过MCP客户端获取数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.logger import setup_logger
from src.ai_orchestrator import create_orchestrator
from src.analysis_tools import get_kline_data, get_latest_price, get_market_ticker
from src.mcp_client import MCPClient

logger = setup_logger()

def test_mcp_client_direct():
    """直接测试MCP客户端"""
    logger.info("=== 测试1: 直接测试MCP客户端 ===")
    
    mcp_client = MCPClient()
    
    # 健康检查
    health = mcp_client.health_check()
    logger.info(f"MCP服务健康检查: {health}")
    
    # 获取缓存统计
    stats = mcp_client.get_cache_stats()
    logger.info(f"缓存统计: {stats}")
    
    # 测试获取K线数据
    result = mcp_client.get_kline_data("BTC-USD-SWAP", "1h", 10)
    logger.info(f"MCP客户端获取K线数据结果: {result['status']}")
    if result['status'] == 'success':
        logger.info(f"数据来源: {'缓存' if result.get('from_cache') else 'MCP服务'}")
    else:
        logger.error(f"获取失败: {result.get('message')}")
    
    return result['status'] == 'success'

def test_analysis_tools():
    """测试analysis_tools中的工具函数"""
    logger.info("=== 测试2: 测试analysis_tools工具函数 ===")
    
    # 测试get_kline_data
    result1 = get_kline_data("BTC-USD-SWAP", "1h", 10)
    logger.info(f"get_kline_data结果: {result1['status']}")
    
    # 测试get_latest_price
    result2 = get_latest_price("BTC-USD-SWAP")
    logger.info(f"get_latest_price结果: {result2['status']}")
    
    # 测试get_market_ticker
    result3 = get_market_ticker("BTC-USD-SWAP")
    logger.info(f"get_market_ticker结果: {result3['status']}")
    
    return all(r['status'] == 'success' for r in [result1, result2, result3])

def test_ai_orchestrator():
    """测试AI编排器的工具适配"""
    logger.info("=== 测试3: 测试AI编排器工具适配 ===")
    
    try:
        orchestrator = create_orchestrator()
        logger.info("AI编排器创建成功")
        
        # 测试工具映射
        tools = orchestrator.get_available_tools()
        logger.info(f"可用工具数量: {len(tools)}")
        
        # 模拟AI工具调用
        test_calls = [
            {
                "name": "get_kline_data",
                "arguments": {"instrument_id": "BTC-USD-SWAP", "granularity": "1h", "max_bars": 5}
            },
            {
                "name": "get_latest_price", 
                "arguments": {"instrument_id": "BTC-USD-SWAP"}
            }
        ]
        
        success_count = 0
        for call in test_calls:
            try:
                # 使用工具映射直接调用方法
                tool_method = orchestrator.tool_mapping.get(call["name"])
                if tool_method:
                    result = tool_method(**call["arguments"])
                    logger.info(f"工具调用 {call['name']}: {result.get('status', 'unknown')}")
                    if result.get('status') == 'success':
                        success_count += 1
                else:
                    logger.error(f"未找到工具方法: {call['name']}")
            except Exception as e:
                logger.error(f"工具调用 {call['name']} 失败: {e}")
        
        return success_count == len(test_calls)
        
    except Exception as e:
        logger.error(f"AI编排器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    logger.info("开始测试MCP架构的完整数据流")
    
    test_results = []
    
    # 测试1: MCP客户端
    test_results.append(("MCP客户端", test_mcp_client_direct()))
    
    # 测试2: 分析工具
    test_results.append(("分析工具", test_analysis_tools()))
    
    # 测试3: AI编排器
    test_results.append(("AI编排器", test_ai_orchestrator()))
    
    # 汇总结果
    logger.info("=== 测试结果汇总 ===")
    passed = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"总体结果: {passed}/{len(test_results)} 测试通过")
    
    if passed == len(test_results):
        logger.info("🎉 MCP架构数据流测试全部通过！")
        return True
    else:
        logger.warning("⚠️ 部分测试失败，需要进一步调试")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)