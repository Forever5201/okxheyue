"""
分析工具集 - 为千问大模型提供数据访问功能
Analysis Tools for Qwen LLM Data Access

为分析代理提供各种数据获取和分析工具，通过MCP服务访问数据
根据Untitled.md设计，LLM通过工具调用获取分析所需的所有数据
"""

import os
import json
import requests
import pandas as pd
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from src.logger import setup_logger

logger = setup_logger()

class AnalysisTools:
    """
    分析工具集类
    为LLM提供各种数据访问和分析功能
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mcp_api_key = os.getenv('MCP_API_KEY')
        self.mcp_base_url = f"http://localhost:{config.get('mcp_service', {}).get('port', 5000)}"
        
        # 工具函数映射
        self.tool_functions = {
            'get_kline_data': self.get_kline_data,
            'get_account_balance': self.get_account_balance,
            'get_positions': self.get_positions,
            'get_market_ticker': self.get_market_ticker,
            'calculate_indicators': self.calculate_indicators,
            'get_timeframe_list': self.get_timeframe_list,
            'get_latest_price': self.get_latest_price,
            'analyze_trend': self.analyze_trend,
        }
        
        logger.info("Analysis Tools initialized")
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        获取工具函数的OpenAI格式schema定义
        用于千问大模型的function calling
        """
        schemas = [
            {
                "type": "function",
                "function": {
                    "name": "get_kline_data",
                    "description": "获取指定时间周期的K线数据，包含价格、成交量和技术指标",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timeframe": {
                                "type": "string",
                                "description": "时间周期 (1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 3d, 1w)",
                                "enum": ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w"]
                            },
                            "limit": {
                                "type": "integer",
                                "description": "返回的数据条数，默认50",
                                "default": 50,
                                "minimum": 1,
                                "maximum": 200
                            }
                        },
                        "required": ["timeframe"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_account_balance",
                    "description": "获取账户余额信息，包含可用余额、总资产等",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_positions",
                    "description": "获取当前持仓信息，包含仓位大小、收益率等",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_market_ticker",
                    "description": "获取市场行情数据，包含最新价格、24小时涨跌幅等",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "交易对符号，默认BTC-USD-SWAP",
                                "default": "BTC-USD-SWAP"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "calculate_indicators",
                    "description": "计算技术指标的汇总信息，包含多个时间周期的指标状态",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timeframes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要分析的时间周期列表",
                                "default": ["1m", "5m", "15m", "30m"]
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_timeframe_list",
                    "description": "获取当前可用的时间周期列表",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_latest_price",
                    "description": "获取最新价格信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {
                                "type": "string",
                                "description": "交易对符号",
                                "default": "BTC-USD-SWAP"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_trend",
                    "description": "分析多个时间周期的趋势方向",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "timeframes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要分析的时间周期",
                                "default": ["1m", "5m", "15m", "30m"]
                            }
                        },
                        "required": []
                    }
                }
            }
        ]
        
        return schemas
    
    def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        调用指定的工具函数
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            Dict[str, Any]: 工具执行结果
        """
        if tool_name not in self.tool_functions:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(self.tool_functions.keys())
            }
        
        try:
            result = self.tool_functions[tool_name](**kwargs)
            logger.info(f"Tool '{tool_name}' executed successfully")
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            return {"success": False, "error": str(e)}
    
    def get_kline_data(self, timeframe: str, limit: int = 50) -> Dict[str, Any]:
        """获取K线数据"""
        try:
            # 通过MCP服务获取数据
            url = f"{self.mcp_base_url}/read_file"
            headers = {"x-api-key": self.mcp_api_key}
            params = {"file_path": f"{timeframe}/{timeframe}.csv"}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                # 解析CSV数据
                import io
                df = pd.read_csv(io.StringIO(response.text))
                
                # 只返回最新的limit条数据
                df_limited = df.tail(limit)
                
                # 转换为更易理解的格式
                result = {
                    "timeframe": timeframe,
                    "data_count": len(df_limited),
                    "latest_price": float(df_limited.iloc[-1]['close']) if not df_limited.empty else None,
                    "price_change_24h": self._calculate_price_change(df_limited),
                    "summary": {
                        "high": float(df_limited['high'].max()),
                        "low": float(df_limited['low'].min()),
                        "volume_avg": float(df_limited['volume'].mean()),
                        "rsi_latest": float(df_limited['rsi'].iloc[-1]) if 'rsi' in df_limited.columns else None,
                        "macd_signal": self._get_macd_signal(df_limited)
                    },
                    "recent_data": df_limited.tail(10).to_dict('records')  # 最近10条数据
                }
                
                return result
            else:
                return {"error": f"Failed to fetch data: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Error fetching K-line data: {str(e)}"}
    
    def get_account_balance(self) -> Dict[str, Any]:
        """获取账户余额"""
        try:
            # 通过MCP服务获取账户信息
            url = f"{self.mcp_base_url}/get_account_info"
            headers = {"x-api-key": self.mcp_api_key}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "balance_info": data.get("balance", {}),
                    "total_equity": data.get("total_equity", 0),
                    "available_balance": data.get("available_balance", 0),
                    "margin_used": data.get("margin_used", 0),
                    "margin_ratio": data.get("margin_ratio", 0)
                }
            else:
                return {"error": "Failed to fetch account balance", "status": response.status_code}
                
        except Exception as e:
            return {"error": f"Error fetching account balance: {str(e)}"}
    
    def get_positions(self) -> Dict[str, Any]:
        """获取持仓信息"""
        try:
            url = f"{self.mcp_base_url}/get_positions"
            headers = {"x-api-key": self.mcp_api_key}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "positions": data.get("positions", []),
                    "total_positions": len(data.get("positions", [])),
                    "total_pnl": sum(pos.get("unrealized_pnl", 0) for pos in data.get("positions", [])),
                    "position_summary": self._summarize_positions(data.get("positions", []))
                }
            else:
                return {"error": "Failed to fetch positions", "status": response.status_code}
                
        except Exception as e:
            return {"error": f"Error fetching positions: {str(e)}"}
    
    def get_market_ticker(self, symbol: str = "BTC-USD-SWAP") -> Dict[str, Any]:
        """获取市场行情"""
        try:
            url = f"{self.mcp_base_url}/get_market_ticker"
            headers = {"x-api-key": self.mcp_api_key}
            params = {"symbol": symbol}
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "symbol": symbol,
                    "latest_price": data.get("last_price"),
                    "change_24h": data.get("change_24h"),
                    "volume_24h": data.get("volume_24h"),
                    "high_24h": data.get("high_24h"),
                    "low_24h": data.get("low_24h"),
                    "funding_rate": data.get("funding_rate")
                }
            else:
                return {"error": "Failed to fetch market ticker", "status": response.status_code}
                
        except Exception as e:
            return {"error": f"Error fetching market ticker: {str(e)}"}
    
    def calculate_indicators(self, timeframes: Optional[List[str]] = None) -> Dict[str, Any]:
        """计算技术指标汇总"""
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "30m"]
        
        results = {}
        for tf in timeframes:
            kline_data = self.get_kline_data(tf, limit=100)
            if kline_data.get("success", True):  # 假设成功除非明确失败
                results[tf] = {
                    "rsi": kline_data.get("summary", {}).get("rsi_latest"),
                    "macd_signal": kline_data.get("summary", {}).get("macd_signal"),
                    "trend": self._determine_trend(kline_data)
                }
        
        return {
            "timeframe_analysis": results,
            "overall_sentiment": self._calculate_overall_sentiment(results)
        }
    
    def get_timeframe_list(self) -> Dict[str, Any]:
        """获取可用时间周期列表"""
        try:
            url = f"{self.mcp_base_url}/list_allowed_files"
            headers = {"x-api-key": self.mcp_api_key}
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                files = data.get("files", [])
                
                # 提取时间周期
                timeframes = []
                for file_info in files:
                    filename = file_info.get("name", "")
                    if filename.endswith(".csv"):
                        tf = filename.split("/")[0] if "/" in filename else filename.replace(".csv", "")
                        if tf not in timeframes:
                            timeframes.append(tf)
                
                return {
                    "available_timeframes": sorted(timeframes),
                    "total_files": len(files),
                    "file_details": files
                }
            else:
                return {"error": "Failed to fetch timeframe list", "status": response.status_code}
                
        except Exception as e:
            return {"error": f"Error fetching timeframe list: {str(e)}"}
    
    def get_latest_price(self, symbol: str = "BTC-USD-SWAP") -> Dict[str, Any]:
        """获取最新价格"""
        ticker_data = self.get_market_ticker(symbol)
        if "error" not in ticker_data:
            return {
                "symbol": symbol,
                "price": ticker_data.get("latest_price"),
                "change_24h": ticker_data.get("change_24h"),
                "timestamp": datetime.now().isoformat()
            }
        return ticker_data
    
    def analyze_trend(self, timeframes: Optional[List[str]] = None) -> Dict[str, Any]:
        """分析多时间周期趋势"""
        if timeframes is None:
            timeframes = ["1m", "5m", "15m", "30m"]
        
        trend_analysis = {}
        for tf in timeframes:
            kline_data = self.get_kline_data(tf, limit=50)
            trend_analysis[tf] = self._determine_trend(kline_data)
        
        return {
            "timeframe_trends": trend_analysis,
            "consensus_trend": self._get_consensus_trend(trend_analysis),
            "trend_strength": self._calculate_trend_strength(trend_analysis)
        }
    
    # 辅助方法
    def _calculate_price_change(self, df: pd.DataFrame) -> float:
        """计算价格变化百分比"""
        if len(df) < 2:
            return 0
        first_price = df.iloc[0]['close']
        last_price = df.iloc[-1]['close']
        return ((last_price - first_price) / first_price) * 100
    
    def _get_macd_signal(self, df: pd.DataFrame) -> str:
        """获取MACD信号"""
        if 'macd' not in df.columns or 'macd_signal' not in df.columns:
            return "unknown"
        
        latest_macd = df['macd'].iloc[-1]
        latest_signal = df['macd_signal'].iloc[-1]
        
        if latest_macd > latest_signal:
            return "bullish"
        elif latest_macd < latest_signal:
            return "bearish"
        else:
            return "neutral"
    
    def _summarize_positions(self, positions: List[Dict]) -> Dict[str, Any]:
        """汇总持仓信息"""
        if not positions:
            return {"total_positions": 0, "net_pnl": 0}
        
        long_positions = [p for p in positions if p.get("side") == "long"]
        short_positions = [p for p in positions if p.get("side") == "short"]
        
        return {
            "long_positions": len(long_positions),
            "short_positions": len(short_positions),
            "total_size": sum(abs(float(p.get("size", 0))) for p in positions),
            "net_pnl": sum(float(p.get("unrealized_pnl", 0)) for p in positions)
        }
    
    def _determine_trend(self, kline_data: Dict[str, Any]) -> str:
        """确定趋势方向"""
        if "error" in kline_data:
            return "unknown"
        
        recent_data = kline_data.get("recent_data", [])
        if len(recent_data) < 5:
            return "insufficient_data"
        
        # 简单趋势判断：比较最近几个收盘价
        prices = [float(d['close']) for d in recent_data[-5:]]
        
        if prices[-1] > prices[0] and sum(prices[i] > prices[i-1] for i in range(1, len(prices))) >= 3:
            return "uptrend"
        elif prices[-1] < prices[0] and sum(prices[i] < prices[i-1] for i in range(1, len(prices))) >= 3:
            return "downtrend"
        else:
            return "sideways"
    
    def _calculate_overall_sentiment(self, results: Dict) -> str:
        """计算整体市场情绪"""
        bullish_count = 0
        bearish_count = 0
        
        for tf_data in results.values():
            if tf_data.get("trend") == "uptrend":
                bullish_count += 1
            elif tf_data.get("trend") == "downtrend":
                bearish_count += 1
        
        if bullish_count > bearish_count:
            return "bullish"
        elif bearish_count > bullish_count:
            return "bearish"
        else:
            return "neutral"
    
    def _get_consensus_trend(self, trend_analysis: Dict) -> str:
        """获取趋势共识"""
        trends = list(trend_analysis.values())
        uptrend_count = trends.count("uptrend")
        downtrend_count = trends.count("downtrend")
        
        if uptrend_count > len(trends) / 2:
            return "uptrend"
        elif downtrend_count > len(trends) / 2:
            return "downtrend"
        else:
            return "mixed"
    
    def _calculate_trend_strength(self, trend_analysis: Dict) -> float:
        """计算趋势强度"""
        trends = list(trend_analysis.values())
        if not trends:
            return 0.0
        
        trend_counts = {}
        for trend in trends:
            trend_counts[trend] = trend_counts.get(trend, 0) + 1
        
        max_count = max(trend_counts.values())
        return max_count / len(trends)