from okx.api import API, Account
from src.logger import setup_logger
import json
import os
import requests
import time
from urllib.parse import urlparse

logger = setup_logger()

# --- Begin: Enhanced network configuration and diagnostics ---

class NetworkDiagnostics:
    """网络诊断和自动修复工具"""
    
    @staticmethod
    def test_connectivity(host="www.okx.com", port=443, timeout=5):
        """测试网络连接性"""
        import socket
        try:
            socket.setdefaulttimeout(timeout)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    @staticmethod
    def detect_proxy_issues():
        """检测代理配置问题"""
        proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']
        issues = []
        
        for var in proxy_vars:
            value = os.environ.get(var)
            if value:
                try:
                    parsed = urlparse(value)
                    if not parsed.hostname:
                        issues.append(f"Invalid proxy URL format: {var}={value}")
                    elif not NetworkDiagnostics.test_connectivity(parsed.hostname, parsed.port or 8080, 3):
                        issues.append(f"Proxy server unreachable: {var}={value}")
                except Exception as e:
                    issues.append(f"Proxy URL parsing failed: {var}={value}, error: {e}")
        
        return issues
    
    @staticmethod
    def apply_network_fixes():
        """应用网络修复策略"""
        fixes_applied = []
        
        # 检测并修复代理问题
        proxy_issues = NetworkDiagnostics.detect_proxy_issues()
        if proxy_issues:
            logger.warning(f"Detected proxy issues: {proxy_issues}")
            
            # 临时清除有问题的代理设置
            proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'proxies', 'PROXIES']
            for var in proxy_vars:
                if os.environ.get(var):
                    old_value = os.environ.pop(var, None)
                    fixes_applied.append(f"Removed problematic proxy: {var}={old_value}")
        
        # 测试基础连接性
        if not NetworkDiagnostics.test_connectivity():
            logger.error("Basic connectivity test failed for www.okx.com:443")
            fixes_applied.append("Basic connectivity check failed")
        else:
            fixes_applied.append("Basic connectivity confirmed")
        
        return fixes_applied

# --- Begin: Defensive network configuration to prevent proxies type errors ---

def _coerce_to_requests_proxies(proxies_value):
    """
    Convert various proxy representations into the dict format expected by requests.
    Accepts None, dict, JSON-string dict, or a single URL string. Returns dict or None.
    """
    if proxies_value is None:
        return None
    if isinstance(proxies_value, dict):
        return proxies_value
    if isinstance(proxies_value, str):
        text = proxies_value.strip()
        if not text:
            return None
        # Attempt to parse JSON object string first
        try:
            if text.startswith("{") and text.endswith("}"):
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass
        # Fallback: treat as one proxy URL for both http and https
        return {"http": text, "https": text}
    # Unknown types are ignored
    return None


def _install_requests_proxies_sanitizer_once():
    """
    Patch requests' Session.request to sanitize a string 'proxies' argument into a dict.
    Prevents AttributeError: 'str' object has no attribute 'get' inside requests.
    """
    sentinel_attr = "_request_patched_for_proxies"
    if getattr(requests.sessions.Session, sentinel_attr, False):
        return

    original_request = requests.sessions.Session.request

    def request_with_sanitized_proxies(self, method, url, **kwargs):
        if "proxies" in kwargs:
            kwargs["proxies"] = _coerce_to_requests_proxies(kwargs["proxies"])
        return original_request(self, method, url, **kwargs)

    # 安全地设置属性，避免类型检查问题
    setattr(requests.sessions.Session, 'request', request_with_sanitized_proxies)
    setattr(requests.sessions.Session, sentinel_attr, True)


# Remove a non-standard env var that some SDKs might incorrectly read as a literal string
for env_key in ("proxies", "PROXIES"):
    if os.environ.get(env_key):
        os.environ.pop(env_key, None)

_install_requests_proxies_sanitizer_once()

# --- End: Defensive network configuration ---

class AccountFetcher:
    def __init__(self, api_key, secret_key, passphrase, flag="0"):
        """
        初始化账户API客户端
        Args:
            api_key (str): OKX API密钥
            secret_key (str): OKX API密钥
            passphrase (str): OKX API口令
            flag (str, optional): 交易模式,'0'为实盘,'1'为模拟盘. Defaults to "0".
        """
        # 应用网络修复策略
        try:
            fixes = NetworkDiagnostics.apply_network_fixes()
            if fixes:
                logger.info(f"Applied network fixes: {fixes}")
        except Exception as e:
            logger.warning(f"Network diagnostics failed: {e}")
        
        # 正确初始化OKX账户API客户端
        self.client = Account(api_key, secret_key, passphrase, "0", flag)
        
        # 网络重试配置
        self.max_retries = 3
        self.retry_delay = 2  # 秒
        self.timeout = 30  # 秒
    
    def _robust_api_call(self, api_method, method_name, *args, **kwargs):
        """
        带有重试机制和网络诊断的API调用
        
        Args:
            api_method: 要调用的API方法
            method_name: 方法名称（用于日志）
            *args, **kwargs: API方法的参数
        
        Returns:
            API响应数据
        
        Raises:
            Exception: 所有重试失败后抛出异常
        """
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Attempting {method_name} (attempt {attempt + 1}/{self.max_retries})")
                response = api_method(*args, **kwargs)
                
                # 成功后记录并返回
                if attempt > 0:
                    logger.info(f"{method_name} succeeded on attempt {attempt + 1}")
                return response
                
            except Exception as e:
                last_exception = e
                error_msg = str(e)
                
                # 分析错误类型
                if "ProxyError" in error_msg or "getaddrinfo failed" in error_msg:
                    logger.warning(f"{method_name} attempt {attempt + 1} failed with network error: {error_msg}")
                    
                    # 在网络错误时尝试修复
                    if attempt < self.max_retries - 1:
                        try:
                            fixes = NetworkDiagnostics.apply_network_fixes()
                            if fixes:
                                logger.info(f"Applied network fixes before retry: {fixes}")
                        except Exception as fix_error:
                            logger.warning(f"Network fix attempt failed: {fix_error}")
                        
                        # 递增延迟
                        delay = self.retry_delay * (attempt + 1)
                        logger.info(f"Waiting {delay} seconds before retry...")
                        time.sleep(delay)
                    
                else:
                    # 非网络错误，直接抛出
                    logger.error(f"{method_name} failed with non-network error: {error_msg}")
                    raise e
        
        # 所有重试都失败
        error_msg = f"{method_name} failed after {self.max_retries} attempts"
        if last_exception:
            error_msg += f". Last error: {last_exception}"
            logger.error(error_msg)
            raise last_exception
        else:
            logger.error(error_msg)
            raise Exception(error_msg)

    def _safe_float(self, value, default=0.0):
        """
        安全地将值转换为浮点数
        Args:
            value: 要转换的值
            default (float, optional): 转换失败时的默认值. Defaults to 0.0.
        Returns:
            float: 转换后的浮点数
        """
        try:
            if value is None or value == '':
                return default
            return float(value)
        except (ValueError, TypeError):
            return default

    def _validate_response(self, response):
        """
        验证API响应的有效性
        Args:
            response: API响应数据
        Returns:
            dict: 验证后的账户数据
        Raises:
            ValueError: 响应数据无效时抛出
        """
        if not response:
            raise ValueError("Empty response received")
        if "data" not in response:
            raise ValueError("Invalid response format - missing 'data' field")
        if not response["data"]:
            raise ValueError("No data available in response")
        return response["data"][0]

    def get_balance(self):
        """
        获取扩展的账户余额信息
        Returns:
            dict: 账户详细余额数据
        """
        try:
            # 使用带重试机制的API调用
            response = self._robust_api_call(self.client.get_balance, "get_balance")
            logger.debug(f"Raw account balance response: {json.dumps(response, indent=2)}")
            
            try:
                account_data = self._validate_response(response)
            except ValueError as ve:
                logger.error(f"Invalid response structure: {ve}")
                return self._get_empty_balance()

            logger.debug(f"Available account fields: {account_data.keys()}")

            # 预处理关键数据
            total_equity = self._safe_float(account_data.get("totalEq"))
            available_equity = self._safe_float(account_data.get("availEq"))
            equity = self._safe_float(account_data.get("eq"))
            margin_frozen = self._safe_float(account_data.get("frozenBal"))
            
            # 数据验证和警告
            self._validate_balance_data({
                "totalEq": total_equity,
                "availEq": available_equity,
                "eq": equity
            })

            # 计算实际可用余额
            corrected_available = self._calculate_available_balance(
                total_equity, margin_frozen, available_equity
            )

            result = {
                "balance": total_equity,
                "available_balance": corrected_available,
                "currency": account_data.get("ccy", "USDT"),
                "margin_frozen": margin_frozen,
                "margin_ratio": self._safe_float(account_data.get("mgnRatio")),
                "unrealized_pnl": self._safe_float(account_data.get("upl")),
                "total_equity": total_equity,
                "account_risk": self._safe_float(account_data.get("adjEq")),
                "maintenance_margin": self._safe_float(account_data.get("mmr"))
            }

            # 验证并修正最终数据
            result = self._validate_and_correct_balance(result)

            logger.info(f"""
            Final balance details:
            - Total Balance: {result['balance']}
            - Available Balance: {result['available_balance']}
            - Margin Ratio: {result['margin_ratio']}
            - Unrealized PNL: {result['unrealized_pnl']}
            - Total Equity: {result['total_equity']}
            """)

            return result

        except Exception as e:
            logger.error(f"Error fetching account balance: {e}", exc_info=True)
            return self._get_empty_balance()

    def _validate_balance_data(self, data):
        """
        验证账户余额数据的合理性
        Args:
            data (dict): 账户数据
        """
        warnings = []
        total_eq = self._safe_float(data.get("totalEq"))
        
        if total_eq > 0:
            if self._safe_float(data.get("availEq")) == 0:
                warnings.append("Total equity > 0 but available equity = 0")
            if self._safe_float(data.get("eq")) == 0:
                warnings.append("Total equity > 0 but equity = 0")

        for warning in warnings:
            logger.warning(f"Data validation warning: {warning}")

    def _calculate_available_balance(self, total_equity, margin_frozen, raw_available):
        """
        计算实际可用余额
        Args:
            total_equity (float): 总权益
            margin_frozen (float): 冻结保证金
            raw_available (float): 原始可用余额
        Returns:
            float: 计算后的可用余额
        """
        if total_equity > 0 and raw_available == 0:
            calculated_available = max(0, total_equity - margin_frozen)
            logger.info(f"Recalculated available balance: {calculated_available} (total_equity: {total_equity}, margin_frozen: {margin_frozen})")
            return calculated_available
        return raw_available

    def _validate_and_correct_balance(self, balance_data):
        """
        验证并修正账户余额数据
        Args:
            balance_data (dict): 账户余额数据
        Returns:
            dict: 修正后的账户余额数据
        """
        total_equity = balance_data["balance"]
        
        if total_equity > 0:
            if balance_data["available_balance"] > total_equity:
                balance_data["available_balance"] = total_equity
                logger.info(f"Corrected available balance from {balance_data['available_balance']} to {total_equity}")

            balance_data["total_equity"] = total_equity
            
            logger.debug(f"""
            Balance data after correction:
            - Total Equity: {balance_data['total_equity']}
            - Available Balance: {balance_data['available_balance']}
            - Margin Frozen: {balance_data['margin_frozen']}
            """)

        return balance_data

    def _get_empty_balance(self):
        """
        返回空的账户余额数据结构
        Returns:
            dict: 包含默认值的账户余额数据
        """
        return {
            "balance": 0.0,
            "available_balance": 0.0,
            "currency": "USDT",
            "margin_frozen": 0.0,
            "margin_ratio": 0.0,
            "unrealized_pnl": 0.0,
            "total_equity": 0.0,
            "account_risk": 0.0,
            "maintenance_margin": 0.0
        }

    def get_detailed_positions(self):
        """
        获取详细的持仓信息
        Returns:
            list: 持仓数据列表
        """
        try:
            # 使用带重试机制的API调用
            response = self._robust_api_call(self.client.get_positions, "get_positions")
            logger.debug(f"Raw positions response: {json.dumps(response, indent=2)}")

            if not response or "data" not in response:
                logger.warning("No position data found in response")
                return []

            positions = []
            for pos in response.get("data", []):
                try:
                    position = {
                        "symbol": pos.get("instId", ""),
                        "position_side": pos.get("posSide", ""),
                        "margin_mode": pos.get("mgnMode", ""),
                        "leverage": self._safe_float(pos.get("lever")),
                        "position_amount": self._safe_float(pos.get("pos")),
                        "available_position": self._safe_float(pos.get("availPos")),
                        "avg_price": self._safe_float(pos.get("avgPx")),
                        "mark_price": self._safe_float(pos.get("markPx")),
                        "unrealized_pnl": self._safe_float(pos.get("upl")),
                        "unrealized_pnl_ratio": self._safe_float(pos.get("uplRatio")),
                        "margin_ratio": self._safe_float(pos.get("mgnRatio")),
                        "margin": self._process_margin_data(pos),
                        "liquidation_price": self._safe_float(pos.get("liqPx")),
                        "position_value": self._safe_float(pos.get("notionalUsd")),
                        "adl_level": int(pos.get("adl", 0)),
                        "created_time": pos.get("cTime", ""),
                        "updated_time": pos.get("uTime", ""),
                        "last_trade_id": pos.get("tradeId", ""),
                        "risk_metrics": self._process_risk_metrics(pos),
                        "stop_orders": self._process_stop_orders(pos)
                    }
                    positions.append(position)

                except Exception as e:
                    logger.error(f"Error processing position data: {e}", exc_info=True)
                    continue

            return positions

        except Exception as e:
            logger.error(f"Error fetching detailed positions: {e}", exc_info=True)
            return []

    def _process_margin_data(self, pos):
        """
        处理保证金相关数据
        """
        return {
            "initial": self._safe_float(pos.get("imr")),
            "maintenance": self._safe_float(pos.get("mmr")),
            "margin_balance": self._safe_float(pos.get("margin"))
        }

    def _process_risk_metrics(self, pos):
        """
        处理风险指标数据
        """
        return {
            "delta_bs": pos.get("deltaBS", ""),
            "gamma_bs": pos.get("gammaBS", ""),
            "theta_bs": pos.get("thetaBS", ""),
            "vega_bs": pos.get("vegaBS", "")
        }

    def _process_stop_orders(self, pos):
        """
        处理止盈止损订单数据
        """
        stop_orders = []
        if "closeOrderAlgo" in pos and pos["closeOrderAlgo"]:
            for algo in pos["closeOrderAlgo"]:
                order_info = {
                    "type": "stop_loss" if "slTriggerPx" in algo else "take_profit",
                    "trigger_price": self._safe_float(
                        algo.get("slTriggerPx") or algo.get("tpTriggerPx")
                    ),
                    "trigger_type": (
                        algo.get("slTriggerPxType") or algo.get("tpTriggerPxType")
                    ),
                    "size": self._safe_float(algo.get("sz"))
                }
                stop_orders.append(order_info)
        return stop_orders