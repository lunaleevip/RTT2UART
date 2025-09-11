# XexunRTT macOS 跨平台构建指南

## 🌍 概述

此指南帮助您在 Windows 或 Linux 系统上为 macOS 构建 XexunRTT 应用程序。

## 🏗️ 构建流程

### 第一步：跨平台构建（在任何系统上）

1. **准备环境**
   ```bash
   python -m pip install pyinstaller>=6.0.0
   python -m pip install -r requirements.txt
   ```

2. **执行跨平台构建**
   ```bash
   python build_cross_platform.py
   ```

3. **检查输出**
   - 构建完成后会在 `dist_macos/` 目录生成文件
   - 文件结构可能不是完整的 .app 格式

### 第二步：最终打包（需要在 macOS 上）

1. **传输文件到 macOS**
   - 将整个 `dist_macos/` 目录复制到 macOS 系统
   - 同时复制 `package_macos.sh` 脚本

2. **在 macOS 上完成打包**
   ```bash
   chmod +x package_macos.sh
   ./package_macos.sh
   ```

3. **获得最终应用**
   - 生成 `XexunRTT.app` 应用程序包
   - 可选择创建 DMG 安装包

## 🔧 替代方案

### 方案一：使用 GitHub Actions

创建 `.github/workflows/build-macos.yml`：

```yaml
name: Build macOS App

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: macos-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pyinstaller>=6.0.0
    
    - name: Build macOS app
      run: python build_macos.py
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: XexunRTT-macOS
        path: dist/
```

### 方案二：使用 Docker（实验性）

```dockerfile
# Dockerfile.macos
FROM sickcodes/docker-osx:auto

# 安装构建依赖
RUN brew install python@3.11

# 复制源代码
COPY . /app
WORKDIR /app

# 构建应用
RUN python build_macos.py
```

### 方案三：云构建服务

- **CircleCI**：支持 macOS 构建环境
- **Travis CI**：提供 macOS 虚拟机
- **Azure DevOps**：有 macOS 代理

## 📋 注意事项

### 跨平台限制
- PyInstaller 的 BUNDLE 功能仅在 macOS 上可用
- 某些 macOS 特定的库可能在其他平台上不可用
- 生成的应用程序包需要在 macOS 上进行最终整理

### 依赖问题
- J-Link 驱动在不同平台上的表现可能不同
- PySide6 的某些模块可能有平台特定的要求
- 确保所有依赖项支持 macOS

### 测试建议
- 在构建完成后，务必在真实的 macOS 设备上测试
- 测试不同版本的 macOS（10.13+）
- 验证 J-Link 连接和 RTT 功能

## 🛠️ 故障排除

### 构建失败
1. 检查 Python 版本是否兼容
2. 确保所有依赖项已正确安装
3. 查看 PyInstaller 详细错误信息

### 应用无法运行
1. 检查 Info.plist 配置
2. 验证可执行文件权限
3. 确保所有依赖库已包含

### 权限问题
1. 在 macOS 上设置正确的可执行权限
2. 处理 Gatekeeper 安全警告
3. 考虑代码签名（付费开发者账户）

## 📞 获取帮助

如果遇到问题，请：
1. 查看构建日志中的详细错误信息
2. 在 GitHub Issues 中搜索类似问题
3. 提供完整的错误日志和系统信息

---

© 2025 Xexun Technology
