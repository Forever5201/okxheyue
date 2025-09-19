import logging
from logging.handlers import RotatingFileHandler
import os
from dotenv import load_dotenv

def setup_logger(logger_name=None):
    """
    配置日志记录器，输出到控制台和文件，避免重复添加处理器。
    :param logger_name: 可选的日志器名称，默认为"TradingBotLogger"
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
    if logger_name is None:
        logger_name = "TradingBotLogger"
    logger = logging.getLogger(logger_name)

    # 如果已经存在处理器，避免重复添加
    if logger.hasHandlers():
        return logger

    # 设置日志级别
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # 设置日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 控制台日志处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 文件日志处理器（自动分割日志文件）
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # 添加处理器到日志对象
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
