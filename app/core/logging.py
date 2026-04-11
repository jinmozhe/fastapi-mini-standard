"""
File: app/core/logging.py
Description: 全局日志配置模块 (Loguru)

本模块负责：
1. 替代 Python 标准库 logging，接管 Uvicorn/FastAPI 日志
2. 配置 Loguru 的输出格式（开发环境文本，生产环境 JSON）
3. 设置日志轮转 (Rotation) 和保留 (Retention) 策略
4. 确保所有日志包含 request_id（由中间件注入）

Author: jinmozhe
Created: 2025-11-24
"""

import logging
import sys
from pathlib import Path
from typing import Any

from loguru import logger

from app.core.config import settings


class InterceptHandler(logging.Handler):
    """
    将 Python 标准库 logging 拦截并转发到 Loguru 的 Handler。
    用于接管 Uvicorn / FastAPI 的内部日志。
    """

    def emit(self, record: logging.LogRecord) -> None:
        # 获取对应的 Loguru 日志级别
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找调用者的栈帧，以确保日志行号正确
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            if frame.f_back:
                frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def format_record(record: dict[str, Any]) -> str:
    """
    自定义日志格式函数。
    如果在 context 中存在 request_id，则将其包含在日志中。
    """
    format_string = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    if record["extra"].get("request_id"):
        format_string += " | <magenta>req_id={extra[request_id]}</magenta>"

    format_string += "\n{exception}"
    return format_string


def setup_logging() -> None:
    """
    初始化日志配置。
    应在 main.py 启动时调用。
    """
    # 1. 拦截标准库日志 (Uvicorn / FastAPI)
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(settings.LOG_LEVEL)

    # 移除 Uvicorn 默认的 handlers，避免重复打印
    for name in logging.root.manager.loggerDict.keys():
        if name.startswith("uvicorn.") or name.startswith("fastapi."):
            logging.getLogger(name).handlers = []
            logging.getLogger(name).propagate = True

    # 2. 配置 Loguru Sink
    logger.remove()

    # 通用配置
    base_config: dict[str, Any] = {
        "level": settings.LOG_LEVEL,
        "enqueue": True,  # 异步写入，生产环境必须
        "backtrace": True,
        "diagnose": settings.LOG_DIAGNOSE,
    }

    # ----------------------------------------------------------------------
    # Sink 1: 控制台输出 (Stdout)
    # ----------------------------------------------------------------------
    console_config = base_config.copy()

    if settings.LOG_JSON_FORMAT:
        console_config["serialize"] = True
    else:
        console_config["format"] = format_record
        console_config["colorize"] = True  # 开发环境彩色输出

    logger.add(sys.stdout, **console_config)

    # ----------------------------------------------------------------------
    # Sink 2: 文件输出 (按配置启用，按小时轮转)
    # ----------------------------------------------------------------------
    if settings.LOG_FILE_ENABLED:
        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        # 按小时轮转，文件名包含日期和小时
        log_path = log_dir / "app_{time:YYYY-MM-DD_HH}.log"

        file_config = base_config.copy()
        file_config.update(
            {
                "rotation": settings.LOG_ROTATION,
                "retention": settings.LOG_RETENTION,
                "compression": settings.LOG_COMPRESSION,
            }
        )

        # 文件日志格式
        if settings.LOG_JSON_FORMAT:
            file_config["serialize"] = True
        else:
            file_config["format"] = format_record

        logger.add(str(log_path), **file_config)

    logger.info("Logging configured successfully")
