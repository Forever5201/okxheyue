"""
简化版AI交易系统主程序
Simplified AI Trading System Main Application
"""

import os
import time
import threading
from dotenv import load_dotenv
from src.logger import setup_logger
from src.simple_data_manager import SimpleDataManager
from src.config_loader import ConfigLoader
from src.mcp_service import app as mcp_app

logger = setup_logger()

def start_mcp_service_in_thread():
    """在后台线程中启动MCP服务"""
    try:
        config = ConfigLoader('config/enhanced_config.yaml').load_config()
        mcp_config = config.get('mcp_service', {})
        host = mcp_config.get('host', '0.0.0.0')
        port = mcp_config.get('port', 5000)
        
        import uvicorn
        uvicorn.run(
            mcp_app,
            host=host,
            port=port,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"MCP service error: {e}")

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
        
        # 1. 先启动MCP服务（后台线程）
        print("🌐 启动MCP服务...")
        config = ConfigLoader('config/enhanced_config.yaml').load_config()
        mcp_config = config.get('mcp_service', {})
        host = mcp_config.get('host', '127.0.0.1')
        port = mcp_config.get('port', 5000)
        
        mcp_thread = threading.Thread(target=start_mcp_service_in_thread, daemon=True)
        mcp_thread.start()
        
        # 等待MCP服务启动
        print("⏳ 等待MCP服务启动...")
        time.sleep(3)
        
        # 2. 初始化数据管理器（会自动授权现有文件）
        print("🔧 初始化数据管理器...")
        data_manager = SimpleDataManager()
        
        # 3. 获取新数据（会自动授权新文件）
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
        
        # 显示MCP服务状态
        print(f"\n🌐 MCP服务运行在: http://{host}:{port}")
        print("📡 AI可以通过MCP协议访问交易数据")
        print("\n" + "=" * 60)
        print("系统运行中... 按 Ctrl+C 停止")
        print("=" * 60)
        
        # 保持主程序运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 用户终止程序")
        
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