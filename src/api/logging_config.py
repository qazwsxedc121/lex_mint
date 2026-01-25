"""集中的日志配置模块"""

import logging
import sys

# 是否已经初始化
_initialized = False

def setup_logging():
    """配置应用日志系统"""
    global _initialized

    if _initialized:
        return

    # 配置根日志器
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True,  # 强制重新配置，覆盖uvicorn的默认配置
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # 设置特定模块的日志级别
    logging.getLogger('src').setLevel(logging.INFO)
    logging.getLogger('llm_interactions').setLevel(logging.INFO)

    # 降低一些第三方库的日志级别
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)

    _initialized = True

    logger = logging.getLogger(__name__)
    logger.info("=" * 80)
    logger.info("日志系统初始化完成")
    logger.info("=" * 80)
