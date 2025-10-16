"""
版本信息配置文件
"""
import datetime

# 应用版本号
VERSION = "2.3"

# 版本名称
VERSION_NAME = "XexunRTT"

# 编译时期（自动生成）
BUILD_TIME = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
    print(ABOUT_TEXT)
