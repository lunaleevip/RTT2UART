"""
版本信息配置文件
"""

import logging
logger = logging.getLogger(__name__)

# 应用版本号
VERSION = "3.1.1"

# 版本名称
VERSION_NAME = "XexunRTT"

# 编译时期（由 build.py 自动更新，无需手动修改）
BUILD_TIME = "2025-11-17 11:45:47"

# 版本描述
VERSION_DESC = f"{VERSION_NAME} v{VERSION}"

# 完整版本信息
FULL_VERSION = f"{VERSION_DESC}\nBuilt: {BUILD_TIME}"

# 关于信息
ABOUT_TEXT = f"""{VERSION_NAME} v{VERSION}

RTT调试工具

基于PySide6

编译时期: {BUILD_TIME}
"""

if __name__ == "__main__":
    logger.debug(ABOUT_TEXT)
