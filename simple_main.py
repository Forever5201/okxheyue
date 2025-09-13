"""
简化版AI交易系统主程序
Simplified AI Trading System Main Application
"""

import os
from dotenv import load_dotenv
from src.logger import setup_logger
from src.simple_data_manager import SimpleDataManager
from src.mcp_service import app as mcp_app

logger = setup_logger()

def main():
    """主函数"""
    print("=" * 60)
    print("🚀 AI Trading System - 简化版")
    print("=" * 60)
    
    try:
        # 加载环境变量
        load_dotenv()
        
        # 检查环境变量
        required_vars = ['OKX_API_KEY', 'OKX_API_SECRET', 'OKX_API_PASSPHRASE', 'MCP_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            print(f"❌ 缺少环境变量: {', '.join(missing_vars)}")
            print("请确保设置了所有必要的API密钥")
            return
        
        # 初始化数据管理器
        print("🔧 初始化系统...")
        data_manager = SimpleDataManager()
        
        # 获取一次数据
        print("📊 获取市场数据...")
        results = data_manager.fetch_and_process_data()
        
        # 显示结果
        successful = len(results.get('success', []))
        failed = len(results.get('failed', []))
        
        print(f"✅ 成功处理: {successful} 个时间周期")
        if failed > 0:
            print(f"❌ 失败: {failed} 个时间周期")
            for fail in results.get('failed', []):
                print(f"   - {fail.get('timeframe')}: {fail.get('reason')}")
        
        # 获取账户和市场信息
        print("💰 获取账户信息...")
        account_info = data_manager.get_account_summary()
        market_info = data_manager.get_market_summary()
        
        # 启动MCP服务
        print("\n🌐 启动MCP服务 (端口 5000)...")
        print("📡 AI可以通过MCP协议访问交易数据")
        print("\n" + "=" * 60)
        print("系统运行中... 按 Ctrl+C 停止")
        print("=" * 60)
        
        # 启动FastAPI服务
        import uvicorn
        uvicorn.run(
            "simple_main:mcp_app",
            host="0.0.0.0",
            port=5000,
            log_level="info",
            reload=False
        )
        
    except KeyboardInterrupt:
        print("\n🛑 用户终止程序")
    except Exception as e:
        print(f"❌ 系统错误: {e}")
        logger.error(f"System error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("👋 系统已停止")

if __name__ == "__main__":
    main()