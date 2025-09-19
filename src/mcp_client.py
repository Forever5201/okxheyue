"""
MCP Client Module
为AI分析提供通过MCP服务访问本地数据的客户端
包括本地缓存机制和数据格式转换适配层
"""

import os
import requests
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.logger import setup_logger

load_dotenv()

MCP_BASE_URL = "http://localhost:8000"
MCP_API_KEY = os.getenv("MCP_API_KEY")

logger = setup_logger()

class MCPClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.cache = {}  # 缓存: key -> (data, timestamp, access_count)
        self.cache_ttl = timedelta(minutes=5)  # 缓存有效期5分钟
        self.max_cache_size = 100  # 最大缓存条目数
        self.request_timeout = 30  # 请求超时时间（秒）
        self.retry_count = 3  # 重试次数
        self.retry_delay = 1  # 重试延迟（秒）
        self.api_key = os.getenv("MCP_API_KEY", "test-api-key-123")
        logger.info(f"MCP客户端初始化: {base_url}，API Key已配置: {'是' if self.api_key else '否'}")
    
    def _get_headers(self):
        """获取请求头，包含API Key"""
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }
    
    def _get_cache_key(self, method: str, params: Dict) -> str:
        """生成缓存键"""
        return f"{method}_{json.dumps(params, sort_keys=True)}"
    
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """检查缓存是否有效"""
        return datetime.now() - timestamp < self.cache_ttl
    
    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """从缓存获取数据"""
        if key in self.cache:
            data, timestamp, access_count = self.cache[key]
            if self._is_cache_valid(timestamp):
                # 更新访问计数
                self.cache[key] = (data, timestamp, access_count + 1)
                logger.debug(f"缓存命中: {key}, 访问次数: {access_count + 1}")
                return data
            else:
                logger.debug(f"缓存过期，删除: {key}")
                del self.cache[key]
        return None
    
    def _set_to_cache(self, key: str, data: Dict):
        """设置缓存，包含LRU清理机制"""
        # 检查缓存大小限制
        if len(self.cache) >= self.max_cache_size:
            self._cleanup_cache()
        
        self.cache[key] = (data, datetime.now(), 1)
        logger.debug(f"数据已缓存: {key}")
    
    def _cleanup_cache(self):
        """清理过期缓存和LRU清理"""
        now = datetime.now()
        expired_keys = []
        
        # 清理过期缓存
        for key, (data, timestamp, access_count) in self.cache.items():
            if now - timestamp >= self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
            logger.debug(f"清理过期缓存: {key}")
        
        # 如果仍然超过限制，使用LRU清理
        if len(self.cache) >= self.max_cache_size:
            # 按访问次数排序，删除最少使用的
            sorted_items = sorted(self.cache.items(), key=lambda x: x[1][2])
            items_to_remove = len(self.cache) - self.max_cache_size + 10  # 多删除10个
            
            for i in range(min(items_to_remove, len(sorted_items))):
                key = sorted_items[i][0]
                del self.cache[key]
                logger.debug(f"LRU清理缓存: {key}")
    
    def clear_cache(self):
        """手动清理所有缓存"""
        cache_size = len(self.cache)
        self.cache.clear()
        logger.info(f"手动清理缓存，删除 {cache_size} 个条目")
    
    def get_kline_data(self, instrument_id: str, granularity: str, max_bars: int = 100) -> Dict:
        """通过MCP获取K线数据，带缓存和重试机制"""
        params = {
            "name": f"{granularity.lower()}/{granularity.lower()}.csv",
            "max_bars": max_bars
        }
        cache_key = self._get_cache_key("get_kline", params)
        
        logger.info(f"请求K线数据: {instrument_id}, 时间周期: {granularity}, 数量: {max_bars}")
        
        # 检查缓存
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            logger.info(f"从缓存返回K线数据: {instrument_id}")
            return {"status": "success", "data": cached, "from_cache": True}
        
        # 重试机制
        last_error = None
        for attempt in range(self.retry_count):
            try:
                headers = self._get_headers()
                
                logger.debug(f"尝试请求MCP服务 (第{attempt + 1}次): {self.base_url}/get_kline")
                
                # 构建请求数据
                request_data = {
                    "name": f"{granularity.lower()}/{granularity.lower()}.csv",
                    "max_bars": max_bars
                }
                
                response = requests.post(
                    f"{self.base_url}/get_kline",
                    json=request_data,
                    headers=headers,
                    timeout=self.request_timeout
                )
                
                # 检查HTTP状态码
                if response.status_code == 200:
                    result = response.json()
                    # MCP服务直接返回数据，格式为 {"file": "...", "data": [...]}
                    if "data" in result:
                        data = result.get("data", [])
                        logger.info(f"成功获取K线数据: {len(data)}条记录")
                        
                        # 缓存结果
                        self._set_to_cache(cache_key, data)
                        return {"status": "success", "data": data, "from_cache": False}
                    else:
                        error_msg = result.get("error", "未知错误")
                        logger.error(f"MCP服务返回错误: {error_msg}")
                        return {"status": "error", "message": f"MCP服务错误: {error_msg}"}
                        
                elif response.status_code == 404:
                    logger.warning(f"数据文件不存在: {instrument_id}_{granularity}")
                    return {"status": "error", "message": "数据文件不存在"}
                    
                elif response.status_code == 401:
                    logger.error("MCP服务认证失败，请检查API密钥")
                    return {"status": "error", "message": "MCP服务认证失败"}
                    
                elif response.status_code == 403:
                    logger.error("MCP服务访问被拒绝，请检查API Key")
                    return {"status": "error", "message": "MCP服务访问被拒绝"}
                    
                else:
                    logger.warning(f"MCP服务返回状态码: {response.status_code}")
                    response.raise_for_status()
                    
            except requests.exceptions.ConnectionError as e:
                last_error = f"连接MCP服务失败: {e}"
                logger.warning(f"连接MCP服务失败 (第{attempt + 1}次): {e}")
            except requests.exceptions.Timeout as e:
                last_error = f"MCP服务请求超时: {e}"
                logger.warning(f"MCP服务请求超时 (第{attempt + 1}次): {e}")
            except requests.exceptions.RequestException as e:
                last_error = f"MCP服务请求异常: {e}"
                logger.warning(f"MCP服务请求异常 (第{attempt + 1}次): {e}")
            except json.JSONDecodeError as e:
                last_error = f"MCP服务响应格式错误: {e}"
                logger.error(f"MCP服务响应格式错误: {e}")
                break  # JSON错误不需要重试
            except Exception as e:
                last_error = f"未知错误: {e}"
                logger.error(f"获取K线数据时发生未知错误: {e}")
                break  # 未知错误不需要重试
            
            # 重试延迟
            if attempt < self.retry_count - 1:
                logger.info(f"等待 {self.retry_delay} 秒后重试...")
                time.sleep(self.retry_delay)
        
        logger.error(f"获取K线数据失败，已重试 {self.retry_count} 次: {last_error}")
        return {"status": "error", "message": last_error}
    
    def health_check(self) -> Dict:
        """检查MCP服务健康状态"""
        try:
            logger.debug("检查MCP服务健康状态")
            response = requests.get(
                f"{self.base_url}/", 
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("MCP服务健康状态正常")
                return {"status": "success", "message": "MCP服务正常运行"}
            else:
                logger.warning(f"MCP服务健康检查失败，状态码: {response.status_code}")
                return {"status": "error", "message": f"MCP服务状态异常: {response.status_code}"}
                
        except requests.exceptions.ConnectionError:
            logger.error("无法连接到MCP服务")
            return {"status": "error", "message": "无法连接到MCP服务"}
        except Exception as e:
            logger.error(f"健康检查异常: {e}")
            return {"status": "error", "message": f"健康检查异常: {e}"}
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        total_items = len(self.cache)
        valid_items = 0
        expired_items = 0
        
        now = datetime.now()
        for key, (data, timestamp, access_count) in self.cache.items():
            if self._is_cache_valid(timestamp):
                valid_items += 1
            else:
                expired_items += 1
        
        stats = {
            "total_items": total_items,
            "valid_items": valid_items,
            "expired_items": expired_items,
            "cache_hit_ratio": "需要实现命中率统计",
            "max_cache_size": self.max_cache_size,
            "cache_ttl_minutes": self.cache_ttl.total_seconds() / 60
        }
        
        logger.debug(f"缓存统计: {stats}")
        return stats
    
    # 可以添加其他方法，如 get_market_ticker 等，如果需要通过MCP路由