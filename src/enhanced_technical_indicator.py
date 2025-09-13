"""
增强的技术指标计算模块
Enhanced Technical Indicator Calculator

支持多种技术指标的计算，基于ta库和自定义算法
"""

import pandas as pd
import numpy as np
import ta
from src.logger import setup_logger

logger = setup_logger()

class EnhancedTechnicalIndicator:
    def __init__(self, params=None):
        """
        初始化技术指标计算器
        
        Args:
            params (dict): 指标参数配置
        """
        self.params = params or {}
        
    def calculate_sma(self, data, periods):
        """计算简单移动平均线"""
        try:
            for period in periods:
                column_name = f'SMA_{period}'
                data[column_name] = data['close'].rolling(window=period).mean()
            logger.info(f"Calculated SMA for periods: {periods}")
            return data
        except Exception as e:
            logger.error(f"Error calculating SMA: {e}")
            return data
    
    def calculate_ema(self, data, periods):
        """计算指数移动平均线"""
        try:
            for period in periods:
                column_name = f'EMA_{period}'
                data[column_name] = data['close'].ewm(span=period).mean()
            logger.info(f"Calculated EMA for periods: {periods}")
            return data
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return data
    
    def calculate_rsi(self, data, period=14):
        """计算相对强弱指数"""
        try:
            data['RSI'] = ta.momentum.rsi(data['close'], window=period)
            logger.info(f"Calculated RSI with period: {period}")
            return data
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return data
    
    def calculate_macd(self, data, fast=12, slow=26, signal=9):
        """计算MACD指标"""
        try:
            macd_line = ta.trend.macd(data['close'], window_slow=slow, window_fast=fast)
            macd_signal = ta.trend.macd_signal(data['close'], window_slow=slow, window_fast=fast, window_sign=signal)
            macd_histogram = ta.trend.macd_diff(data['close'], window_slow=slow, window_fast=fast, window_sign=signal)
            
            data['MACD'] = macd_line
            data['MACD_Signal'] = macd_signal
            data['MACD_Histogram'] = macd_histogram
            
            logger.info(f"Calculated MACD with fast={fast}, slow={slow}, signal={signal}")
            return data
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return data
    
    def calculate_bollinger_bands(self, data, period=20, std_dev=2.0):
        """计算布林带"""
        try:
            bb_upper = ta.volatility.bollinger_hband(data['close'], window=period, window_dev=std_dev)
            bb_middle = ta.volatility.bollinger_mavg(data['close'], window=period)
            bb_lower = ta.volatility.bollinger_lband(data['close'], window=period, window_dev=std_dev)
            
            data['BB_Upper'] = bb_upper
            data['BB_Middle'] = bb_middle
            data['BB_Lower'] = bb_lower
            data['BB_Width'] = bb_upper - bb_lower
            data['BB_Position'] = (data['close'] - bb_lower) / (bb_upper - bb_lower)
            
            logger.info(f"Calculated Bollinger Bands with period={period}, std_dev={std_dev}")
            return data
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return data
    
    def calculate_atr(self, data, period=14):
        """计算平均真实范围"""
        try:
            data['ATR'] = ta.volatility.average_true_range(data['high'], data['low'], data['close'], window=period)
            logger.info(f"Calculated ATR with period: {period}")
            return data
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return data
    
    def calculate_stochastic(self, data, k_period=14, d_period=3, smooth=3):
        """计算随机指标"""
        try:
            stoch_k = ta.momentum.stoch(data['high'], data['low'], data['close'], window=k_period, smooth_window=smooth)
            stoch_d = ta.momentum.stoch_signal(data['high'], data['low'], data['close'], window=k_period, smooth_window=smooth, window_sign=d_period)
            
            data['Stoch_K'] = stoch_k
            data['Stoch_D'] = stoch_d
            
            logger.info(f"Calculated Stochastic with K={k_period}, D={d_period}, smooth={smooth}")
            return data
        except Exception as e:
            logger.error(f"Error calculating Stochastic: {e}")
            return data
    
    def calculate_williams_r(self, data, period=14):
        """计算威廉指标"""
        try:
            data['Williams_R'] = ta.momentum.williams_r(data['high'], data['low'], data['close'], lbp=period)
            logger.info(f"Calculated Williams %R with period: {period}")
            return data
        except Exception as e:
            logger.error(f"Error calculating Williams %R: {e}")
            return data
    
    def calculate_cci(self, data, period=20):
        """计算商品通道指数"""
        try:
            data['CCI'] = ta.trend.cci(data['high'], data['low'], data['close'], window=period)
            logger.info(f"Calculated CCI with period: {period}")
            return data
        except Exception as e:
            logger.error(f"Error calculating CCI: {e}")
            return data
    
    def calculate_volume_indicators(self, data):
        """计算成交量指标"""
        try:
            if 'volume' in data.columns and not data['volume'].isna().all():
                # 成交量加权平均价
                data['VWAP'] = ta.volume.volume_weighted_average_price(data['high'], data['low'], data['close'], data['volume'])
                
                # 成交量RSI
                volume_rsi_period = self.params.get('volume_rsi_period', 14)
                data['Volume_RSI'] = ta.momentum.rsi(data['volume'], window=volume_rsi_period)
                
                # 能量潮指标
                data['OBV'] = ta.volume.on_balance_volume(data['close'], data['volume'])
                
                logger.info("Calculated volume indicators")
            else:
                logger.warning("Volume data not available or empty, skipping volume indicators")
            
            return data
        except Exception as e:
            logger.error(f"Error calculating volume indicators: {e}")
            return data
    
    def calculate_momentum_indicators(self, data):
        """计算动量指标"""
        try:
            # 动量指标
            momentum_period = self.params.get('momentum_period', 10)
            data['Momentum'] = data['close'].diff(momentum_period)
            
            # 变化率ROC
            roc_period = self.params.get('roc_period', 12)
            data['ROC'] = ta.momentum.roc(data['close'], window=roc_period)
            
            logger.info("Calculated momentum indicators")
            return data
        except Exception as e:
            logger.error(f"Error calculating momentum indicators: {e}")
            return data
    
    def calculate_all_indicators(self, data, category="medium_term"):
        """
        计算所有技术指标
        
        Args:
            data (pd.DataFrame): K线数据
            category (str): 指标类别 (short_term, medium_term, long_term)
        
        Returns:
            pd.DataFrame: 包含技术指标的数据
        """
        try:
            logger.info(f"Calculating all indicators for category: {category}")
            
            # 获取配置参数
            config_key = category if category in ['short_term', 'medium_term', 'long_term'] else 'common'
            indicator_config = self.params.get(config_key, self.params.get('common', {}))
            
            # 基础移动平均线
            if 'sma_periods' in indicator_config:
                data = self.calculate_sma(data, indicator_config['sma_periods'])
            
            if 'ema_periods' in indicator_config:
                data = self.calculate_ema(data, indicator_config['ema_periods'])
            
            # 技术指标
            rsi_period = indicator_config.get('rsi_period', 14)
            data = self.calculate_rsi(data, rsi_period)
            
            macd_fast = indicator_config.get('macd_fast', 12)
            macd_slow = indicator_config.get('macd_slow', 26)
            macd_signal = indicator_config.get('macd_signal', 9)
            data = self.calculate_macd(data, macd_fast, macd_slow, macd_signal)
            
            bb_period = indicator_config.get('bb_period', 20)
            bb_std = indicator_config.get('bb_std', 2.0)
            data = self.calculate_bollinger_bands(data, bb_period, bb_std)
            
            atr_period = indicator_config.get('atr_period', 14)
            data = self.calculate_atr(data, atr_period)
            
            # 随机指标
            stoch_k = indicator_config.get('stoch_k', 14)
            stoch_d = indicator_config.get('stoch_d', 3)
            stoch_smooth = indicator_config.get('stoch_smooth', 3)
            data = self.calculate_stochastic(data, stoch_k, stoch_d, stoch_smooth)
            
            # 威廉指标
            williams_period = indicator_config.get('williams_r_period', 14)
            data = self.calculate_williams_r(data, williams_period)
            
            # CCI指标
            cci_period = indicator_config.get('cci_period', 20)
            data = self.calculate_cci(data, cci_period)
            
            # 成交量指标
            data = self.calculate_volume_indicators(data)
            
            # 动量指标
            data = self.calculate_momentum_indicators(data)
            
            logger.info(f"Successfully calculated all indicators for {category}")
            return data
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return data
    
    def add_signal_analysis(self, data):
        """
        添加信号分析
        
        Args:
            data (pd.DataFrame): 包含技术指标的数据
            
        Returns:
            pd.DataFrame: 包含信号分析的数据
        """
        try:
            # RSI信号
            data['RSI_Oversold'] = data['RSI'] < 30
            data['RSI_Overbought'] = data['RSI'] > 70
            
            # MACD信号
            data['MACD_Bullish'] = (data['MACD'] > data['MACD_Signal']) & (data['MACD'].shift(1) <= data['MACD_Signal'].shift(1))
            data['MACD_Bearish'] = (data['MACD'] < data['MACD_Signal']) & (data['MACD'].shift(1) >= data['MACD_Signal'].shift(1))
            
            # 布林带信号
            data['BB_Squeeze'] = (data['BB_Width'] < data['BB_Width'].rolling(20).mean() * 0.8)
            data['BB_Breakout_Upper'] = data['close'] > data['BB_Upper']
            data['BB_Breakout_Lower'] = data['close'] < data['BB_Lower']
            
            # 多重时间框架趋势
            if 'EMA_20' in data.columns and 'EMA_50' in data.columns:
                data['Trend_Bullish'] = data['EMA_20'] > data['EMA_50']
                data['Trend_Bearish'] = data['EMA_20'] < data['EMA_50']
            
            logger.info("Added signal analysis")
            return data
            
        except Exception as e:
            logger.error(f"Error adding signal analysis: {e}")
            return data