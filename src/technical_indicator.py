import pandas as pd
import numpy as np
from src.logger import setup_logger
import pandas_ta as ta  # type: ignore

logger = setup_logger()


class TechnicalIndicator:
    def __init__(self, params):
        self.params = params

    def calculate_all(self, df, category):
        logger.info(f"Calculating indicators for category: {category}")

        # 数据清理
        required_columns = ['close', 'high', 'low', 'volume']
        for col in required_columns:
            if col not in df.columns:
                logger.warning(f"Missing '{col}' column. Filling with default values (0).")
                df[col] = 0.0

        df = df.dropna(subset=['close', 'high', 'low'])  # 清理NaN

        try:
            logger.info("Calculating indicators with pandas_ta...")

            # RSI（尽量对齐旧版：使用 SMA 作为平滑；若版本不支持 mamode，则回退默认）
            try:
                rsi_series = ta.rsi(close=df['close'], length=int(self.params['rsi_window']), talib=False, mamode='sma')
            except TypeError:
                rsi_series = ta.rsi(close=df['close'], length=int(self.params['rsi_window']))
            df['rsi'] = rsi_series.fillna(0).astype(float)

            # Bollinger Bands
            bb = ta.bbands(close=df['close'], length=int(self.params['bollinger_window']), std=float(self.params['bollinger_dev']))
            if bb is not None and not bb.empty:
                lower_col = [c for c in bb.columns if c.startswith('BBL_')]
                upper_col = [c for c in bb.columns if c.startswith('BBU_')]
                df['bollinger_lower'] = bb[lower_col[0]].fillna(0).astype(float) if lower_col else 0.0
                df['bollinger_upper'] = bb[upper_col[0]].fillna(0).astype(float) if upper_col else 0.0
            else:
                df['bollinger_lower'] = 0.0
                df['bollinger_upper'] = 0.0

            # MACD
            macd = ta.macd(close=df['close'], fast=int(self.params['macd_fast']), slow=int(self.params['macd_slow']), signal=int(self.params['macd_signal']))
            if macd is not None and not macd.empty:
                macd_line_col = [c for c in macd.columns if c.startswith('MACD_') and not c.startswith('MACDh_') and not c.startswith('MACDs_')]
                macd_signal_col = [c for c in macd.columns if c.startswith('MACDs_')]
                df['macd'] = macd[macd_line_col[0]].fillna(0).astype(float) if macd_line_col else 0.0
                df['macd_signal'] = macd[macd_signal_col[0]].fillna(0).astype(float) if macd_signal_col else 0.0
            else:
                df['macd'] = 0.0
                df['macd_signal'] = 0.0

            # ATR（与旧版接近：SMA；若不支持 mamode 参数，回退默认）
            try:
                atr_series = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=int(self.params['atr_window']), mamode='sma')
            except TypeError:
                atr_series = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=int(self.params['atr_window']))
            df['atr'] = atr_series.fillna(0).astype(float)

            # VWAP（需要有效的 volume）
            if 'volume' in df.columns and float(df['volume'].sum()) > 0:
                vwap_series = ta.vwap(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'])
                df['vwap'] = vwap_series.fillna(0).astype(float)
            else:
                logger.warning("VWAP skipped due to missing or invalid 'volume' data.")
                df['vwap'] = 0.0

        except Exception as e:
            logger.error(f"pandas_ta calculation failed: {e}", exc_info=True)
            raise

        # 整合指标
        logger.info("Constructing indicators field...")
        df['indicators'] = df.apply(
            lambda row: {
                "rsi": row['rsi'],
                "bollinger_upper": row['bollinger_upper'],
                "bollinger_lower": row['bollinger_lower'],
                "macd": row['macd'],
                "macd_signal": row['macd_signal'],
                "atr": row['atr'],
                "vwap": row['vwap']
            }, axis=1
        )

        # 确保数值型字段不含 NaN
        numeric_columns = ['rsi', 'bollinger_upper', 'bollinger_lower', 'macd', 'macd_signal', 'atr', 'vwap']
        for col in numeric_columns:
            if col not in df.columns:
                df[col] = 0.0
        df[numeric_columns] = df[numeric_columns].fillna(0)

        logger.info("Indicators calculated successfully.")
        return df.reset_index(drop=True)
