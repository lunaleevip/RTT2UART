#!/bin/bash
# XexunRTT 一键构建脚本 (Linux/macOS)

set -e  # 遇到错误立即退出

echo "================================================================"
echo "  XexunRTT 一键构建脚本"
echo "================================================================"
echo

# 读取版本号
VERSION=$(python3 -c "from version import VERSION; print(VERSION)")
echo "[INFO] 当前版本: v$VERSION"
echo

# 步骤1: 更新翻译文件
echo "[1/4] 更新翻译文件..."
echo "----------------------------------------------------------------"
bash update_translations.sh
echo "[OK] 翻译文件更新完成"
echo

# 步骤2: 清理旧的构建文件
echo "[2/4] 清理旧的构建文件..."
echo "----------------------------------------------------------------"
if [ -d "build" ]; then
    echo "删除 build 目录..."
    rm -rf build
fi
if ls dist/XexunRTT*.exe 1> /dev/null 2>&1; then
    echo "删除旧的 EXE 文件..."
    rm -f dist/XexunRTT*.exe
fi
echo "[OK] 清理完成"
echo

# 步骤3: 构建EXE
echo "[3/4] 构建可执行文件..."
echo "----------------------------------------------------------------"
python3 build.py
echo "[OK] 构建完成"
echo

# 步骤4: 显示构建结果
echo "[4/4] 构建结果"
echo "----------------------------------------------------------------"
if [ -f "dist/XexunRTT_v${VERSION}.exe" ]; then
    ls -lh "dist/XexunRTT_v${VERSION}.exe"
fi
echo

echo "================================================================"
echo "  构建完成！"
echo "================================================================"
echo
echo "下一步操作:"
echo "  1. 测试运行: dist/XexunRTT_v${VERSION}.exe"
echo "  2. 提交代码: git add . && git commit"
echo "  3. 创建标签: git tag v${VERSION}"
echo

