#!/bin/bash
# XexunRTT 多开脚本

# 获取当前脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 获取APP路径
APP_PATH="$SCRIPT_DIR/../XexunRTT.app"

# 检查APP是否存在
if [ ! -d "$APP_PATH" ]; then
    echo "错误: 找不到 XexunRTT.app"
    exit 1
fi

# 启动新的APP实例
open -n "$APP_PATH"

echo "✅ 新窗口已启动"
