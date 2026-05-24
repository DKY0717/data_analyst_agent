import logging
import sys
from logging.handlers import RotatingFileHandler  # 滚动文件处理器，当日志文件达到指定大小时自动轮转
from pathlib import Path

from ..config import settings  # 从配置模块导入全局配置对象

def setup_logging() -> logging.Logger:
    """配置应用程序的日志系统

    设置两个日志输出目的地（handler）：
    1. 控制台（终端输出）—— 方便开发时实时查看
    2. 日志文件（自动轮转）—— 方便事后排查问题

    返回值: 配置好的 logger 实例
    """

    # 创建一个名为 "data_analyst_agent" 的 logger 实例
    # 同一个名字调用 getLogger() 会返回同一个对象，避免重复创建
    logger = logging.getLogger("data_analyst_agent")

    # 设置 logger 的最低日志级别（DEBUG / INFO / WARNING / ERROR / CRITICAL）
    # getattr(logging, "INFO") 等价于 logging.INFO，这样可以通过配置文件灵活控制级别
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))

    # 防止重复添加 handler（比如多次调用 setup_logging() 时）
    # 如果已经有 handler 了，直接返回，避免日志重复输出
    if logger.handlers:
        return logger

    # ============ Handler 1: 控制台输出 ============
    # StreamHandler 负责把日志输出到流（这里指定为 sys.stdout，即终端）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # 控制台只输出 INFO 及以上级别（不显示 DEBUG）
    # 日志格式：时间 - 日志名称 - 级别 - 消息内容
    # 例如：2026-05-23 10:00:00 - data_analyst_agent - INFO - 服务启动成功
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)

    # ============ Handler 2: 文件输出（自动轮转） ============
    # 日志文件路径，使用 / 运算符拼接路径（Path 对象的用法）
    # 例如: logs/app.log
    log_file = settings.LOG_DIR / "app.log"

    # RotatingFileHandler: 当日志文件达到 maxBytes 时，自动创建新文件
    # 旧文件会被重命名为 app.log.1, app.log.2, ... 最多保留 backupCount 个备份
    # 这样可以防止单个日志文件无限膨胀撑爆磁盘
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 单个日志文件最大 10MB (10 * 1024 * 1024 字节)
        backupCount=5,               # 最多保留 5 个备份文件（app.log.1 ~ app.log.5）
        encoding='utf-8'             # 使用 UTF-8 编码，确保中文不乱码
    )
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别（包括 DEBUG），方便详细排查
    # 文件日志格式比控制台多了 funcName（函数名）和 lineno（行号），方便定位代码位置
    # 例如：2026-05-23 10:00:00 - data_analyst_agent - DEBUG - fetch_data:42 - 开始获取数据
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_format)

    # 把两个 handler 都挂到 logger 上
    # 之后调用 logger.info() 等方法时，日志会同时输出到控制台和文件
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

# 模块级别初始化：当这个文件被 import 时，自动执行 setup_logging() 并导出 logger
# 其他模块只需 from app.utils.logger import logger 即可直接使用
logger = setup_logging()
