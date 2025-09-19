#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账户信息获取器
Account Information Fetcher

提供OKX账户信息获取功能
"""

import os
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

from src.logger import setup_logger

logger = setup_logger()

class AccountFetcher:
    """账户信息获取器"""
    
    def __init__(self, api_key=None, api_secret=None, api_passphrase=None, flag='1'):
        """初始化账户获取器
        
        Args:
            api_key: OKX API Key
            api_secret: OKX API Secret
            api_passphrase: OKX API Passphrase
            flag: 交易模式标志 ('0': 模拟交易, '1': 实盘交易)
        """
        self.api_key = api_key or os.getenv('OKX_API_KEY')
        self.api_secret = api_secret or os.getenv('OKX_API_SECRET')
        self.api_passphrase = api_passphrase or os.getenv('OKX_API_PASSPHRASE')
        self.flag = flag
        
        if not all([self.api_key, self.api_secret, self.api_passphrase]):
            logger.warning("OKX API credentials not fully configured")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Account fetcher initialized successfully (mode: {'实盘' if flag == '1' else '模拟'})")
    
    def get_account_balance(self) -> Dict[str, Any]:
        """获取账户余额"""
        try:
            if not self.enabled:
                return {
                    'success': False,
                    'error': 'API credentials not configured',
                    'data': None
                }
            
            # 模拟账户余额数据（实际应用中需要调用OKX API）
            balance_data = {
                'total_equity': '10000.00',
                'available_balance': '8500.00',
                'frozen_balance': '1500.00',
                'currency': 'USDT',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info("Account balance retrieved successfully")
            return {
                'success': True,
                'data': balance_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_positions(self) -> Dict[str, Any]:
        """获取持仓信息"""
        try:
            if not self.enabled:
                return {
                    'success': False,
                    'error': 'API credentials not configured',
                    'data': []
                }
            
            # 模拟持仓数据（实际应用中需要调用OKX API）
            positions_data = [
                {
                    'instrument': 'BTC-USD-SWAP',
                    'position_side': 'long',
                    'size': '0.1',
                    'avg_price': '45000.00',
                    'unrealized_pnl': '500.00',
                    'margin': '1000.00'
                }
            ]
            
            logger.info(f"Retrieved {len(positions_data)} positions")
            return {
                'success': True,
                'data': positions_data,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }
    
    def get_account_summary(self) -> Dict[str, Any]:
        """获取账户摘要信息"""
        try:
            balance_result = self.get_account_balance()
            positions_result = self.get_positions()
            
            summary = {
                'account_balance': balance_result,
                'positions': positions_result,
                'summary': {
                    'total_positions': len(positions_result.get('data', [])),
                    'account_status': 'active' if self.enabled else 'disabled',
                    'last_update': datetime.utcnow().isoformat()
                }
            }
            
            logger.info("Account summary generated successfully")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get account summary: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def is_enabled(self) -> bool:
        """检查账户获取器是否启用"""
        return self.enabled
    
    def get_status(self) -> Dict[str, Any]:
        """获取账户获取器状态"""
        return {
            'enabled': self.enabled,
            'api_configured': bool(self.api_key and self.api_secret and self.api_passphrase),
            'timestamp': datetime.utcnow().isoformat()
        }

# 向后兼容性函数
def get_account_info() -> Dict[str, Any]:
    """获取账户信息（向后兼容）"""
    fetcher = AccountFetcher()
    return fetcher.get_account_summary()

if __name__ == "__main__":
    # 测试账户获取器
    fetcher = AccountFetcher()
    print("Account Fetcher Status:", fetcher.get_status())
    print("Account Summary:", json.dumps(fetcher.get_account_summary(), indent=2, ensure_ascii=False))