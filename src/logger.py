import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from dotenv import load_dotenv

class SafeConsoleHandler(logging.StreamHandler):
    """安全的控制台日志处理器，避免Unicode字符编码错误"""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            # 移除emoji和不兼容的Unicode字符
            safe_msg = msg.encode('ascii', errors='ignore').decode('ascii')
            stream = self.stream
            stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

def setup_logger():
    """
    配置日志记录器，输出到控制台和文件，避免重复添加处理器。
    :return: 配置好的日志对象
    """
    # 加载环境变量
    load_dotenv()

    # 从环境变量中读取日志存储路径和日志级别
    log_dir = os.getenv("LOG_DIR", "logs")
    log_file = os.path.join(log_dir, os.getenv("LOG_FILE", "app.log"))
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # 创建日志目录（如果不存在）
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 设置日志对象
    logger = logging.getLogger("TradingBotLogger")

    # 如果已经存在处理器，避免重复添加
    if logger.hasHandlers():
        return logger

    # 设置日志级别
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # 设置日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 控制台日志处理器 - 修复Windows编码问题
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Windows环境下设置UTF-8编码避免emoji字符错误
    if sys.platform.startswith('win'):
        try:
            # 尝试设置控制台为UTF-8编码
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
        except Exception:
            # 如果无法设置UTF-8，使用安全的处理器
            console_handler = SafeConsoleHandler()
            console_handler.setFormatter(formatter)

    # 文件日志处理器（自动分割日志文件）
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    file_handler.setFormatter(formatter)

    # 添加处理器到日志对象
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
