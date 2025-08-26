#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建发布包脚本
包含EXE文件、说明文档和防病毒白名单信息
"""

import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

def create_readme():
    """创建README文档"""
    readme_content = """# XexunRTT v1.0.5 - RTT2UART 调试工具

## 📋 软件简介

XexunRTT是一个专业的RTT(Real Time Transfer)到UART转换调试工具，支持SEGGER J-Link调试器。

## ✨ 主要功能

- 🔗 **RTT到UART转换**：将RTT数据流转换为标准UART输出
- 🖥️ **图形化界面**：基于PySide6的现代化GUI界面
- 🌐 **多语言支持**：支持中文/英文界面切换
- 📊 **实时日志显示**：JLink内部日志实时显示和过滤
- 🎨 **主题切换**：支持明亮/暗黑主题切换
- 🔧 **多种连接方式**：支持USB、TCP/IP连接方式
- 📝 **数据过滤**：支持自定义数据过滤和筛选

## 🚀 快速开始

1. **连接J-Link调试器**到目标设备
2. **运行XexunRTT.exe**
3. **选择连接方式**（USB/TCP）
4. **配置目标设备**和接口参数
5. **点击开始**建立RTT连接

## 📁 文件说明

- `XexunRTT.exe` - 主程序文件
- `README.md` - 使用说明文档
- `ANTIVIRUS_INFO.md` - 防病毒软件说明

## ⚠️ 防病毒软件说明

本软件使用PyInstaller打包，可能被某些杀毒软件误报。这是正常现象，原因如下：

1. **打包工具特征**：PyInstaller等打包工具的特征可能触发启发式检测
2. **网络功能**：软件包含TCP/IP网络通信功能
3. **硬件访问**：需要访问串口和USB设备

### 🛡️ 安全保证

- ✅ 源代码开源，可审查
- ✅ 使用官方Python和第三方库
- ✅ 无恶意代码，无数据收集
- ✅ 仅用于调试和开发目的

### 🔧 解决方案

如果被杀毒软件拦截：

1. **添加白名单**：将XexunRTT.exe添加到杀毒软件白名单
2. **临时关闭**：临时关闭实时防护运行程序
3. **信任发布者**：将软件标记为可信任

## 🔧 系统要求

- **操作系统**：Windows 10/11 (64位)
- **硬件**：SEGGER J-Link调试器
- **权限**：管理员权限（用于访问硬件设备）

## 📞 技术支持

如有问题或建议，请联系开发团队。

## 📄 版权信息

Copyright © 2024 XexunRTT Team
版本：v1.0.5
构建时间：{build_time}
打包工具：PyInstaller {pyinstaller_version}
"""
    
    # 获取PyInstaller版本
    try:
        import PyInstaller
        pyinstaller_version = PyInstaller.__version__
    except:
        pyinstaller_version = "6.15.0"
    
    build_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return readme_content.format(
        build_time=build_time,
        pyinstaller_version=pyinstaller_version
    )

def create_antivirus_info():
    """创建防病毒软件说明"""
    antivirus_content = """# 防病毒软件说明

## 🛡️ 为什么会被杀毒软件报毒？

XexunRTT.exe可能被某些杀毒软件误报为恶意软件，这是**误报**，原因如下：

### 1. 打包工具特征
- 使用PyInstaller将Python程序打包为EXE
- 打包后的程序包含Python解释器和大量库文件
- 杀毒软件可能将这些特征识别为可疑行为

### 2. 网络通信功能
- 程序支持TCP/IP连接到J-Link调试器
- 网络通信功能可能触发网络安全检测

### 3. 硬件设备访问
- 需要访问USB端口和串口设备
- 硬件访问权限可能被视为潜在风险

### 4. 启发式检测
- 现代杀毒软件使用启发式算法检测未知威胁
- 新打包的程序可能触发这些算法

## ✅ 安全保证

### 程序安全性
- **开源代码**：所有源代码可审查，无恶意功能
- **官方库**：仅使用Python官方库和知名第三方库
- **专业用途**：专门用于嵌入式开发和调试
- **无网络上传**：不会上传任何用户数据

### 使用的主要库
- `PySide6`：Qt官方Python绑定，用于GUI界面
- `pylink`：SEGGER官方Python库，用于J-Link通信
- `pyserial`：Python官方串口通信库
- `qdarkstyle`：开源UI主题库

## 🔧 解决方案

### 方案1：添加白名单（推荐）
1. 打开杀毒软件设置
2. 找到"白名单"或"信任区域"设置
3. 添加`XexunRTT.exe`到白名单
4. 重新运行程序

### 方案2：临时关闭防护
1. 临时关闭杀毒软件实时防护
2. 运行XexunRTT.exe
3. 程序启动后重新开启防护

### 方案3：更换杀毒软件
- 推荐使用Windows Defender（误报率较低）
- 或使用对开发工具友好的杀毒软件

## 📊 常见杀毒软件处理方法

### Windows Defender
1. 打开"Windows 安全中心"
2. 点击"病毒和威胁防护"
3. 点击"管理设置"
4. 添加排除项 → 文件 → 选择XexunRTT.exe

### 360安全卫士
1. 打开360安全卫士
2. 点击"木马查杀"
3. 点击"信任区"
4. 添加信任文件

### 火绒安全
1. 打开火绒安全软件
2. 点击"设置"
3. 点击"信任区"
4. 添加信任文件

### 卡巴斯基
1. 打开卡巴斯基
2. 点击"设置"
3. 点击"威胁和排除项"
4. 添加排除项

## 📞 如果仍有问题

如果按照上述方法仍然无法解决，请：

1. **检查文件完整性**：确保下载的文件完整
2. **更新杀毒软件**：使用最新版本的杀毒软件
3. **联系技术支持**：向我们反馈具体的杀毒软件和报错信息

## 🔍 验证文件安全性

您可以通过以下方式验证文件安全性：

1. **VirusTotal扫描**：上传到virustotal.com进行多引擎扫描
2. **文件属性检查**：查看文件的数字签名和属性信息
3. **沙箱分析**：使用在线沙箱分析工具检测行为

---

**重要提醒**：本软件完全安全，误报是由于打包工具的技术特征导致的。请放心使用！
"""
    return antivirus_content

def create_release_package():
    """创建发布包"""
    print("🚀 创建XexunRTT发布包...")
    
    # 检查EXE文件是否存在
    exe_path = Path('dist/XexunRTT.exe')
    if not exe_path.exists():
        print("❌ 错误：未找到XexunRTT.exe文件")
        print("请先运行 build_pyinstaller.py 构建程序")
        return False
    
    # 创建发布目录
    release_dir = Path('release')
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir()
    
    # 复制EXE文件
    print("📦 复制EXE文件...")
    shutil.copy2(exe_path, release_dir / 'XexunRTT.exe')
    
    # 创建文档
    print("📝 创建说明文档...")
    with open(release_dir / 'README.md', 'w', encoding='utf-8') as f:
        f.write(create_readme())
    
    with open(release_dir / 'ANTIVIRUS_INFO.md', 'w', encoding='utf-8') as f:
        f.write(create_antivirus_info())
    
    # 创建启动脚本
    print("🔧 创建启动脚本...")
    startup_script = """@echo off
title XexunRTT v1.0.5 启动器
echo.
echo ========================================
echo   XexunRTT v1.0.5 - RTT2UART调试工具
echo ========================================
echo.
echo 正在启动程序...
echo.

if exist "XexunRTT.exe" (
    echo [OK] 找到程序文件，正在启动...
    start "" "XexunRTT.exe"
    echo.
    echo [OK] 程序已启动！
    echo.
    echo [提示] 如果被杀毒软件拦截，请查看 ANTIVIRUS_INFO.md
) else (
    echo [错误] 未找到 XexunRTT.exe 文件！
    echo.
)

echo.
pause
"""
    
    with open(release_dir / '启动XexunRTT.bat', 'w', encoding='utf-8') as f:
        f.write(startup_script)
    
    # 创建ZIP压缩包
    print("🗜️ 创建ZIP压缩包...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f'XexunRTT_v1.0.5_{timestamp}.zip'
    
    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in release_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(release_dir)
                zipf.write(file_path, arcname)
    
    # 显示结果
    exe_size = exe_path.stat().st_size / (1024 * 1024)
    zip_size = Path(zip_name).stat().st_size / (1024 * 1024)
    
    print("\n🎉 发布包创建完成！")
    print("=" * 50)
    print(f"📁 发布目录: {release_dir.absolute()}")
    print(f"📦 压缩包: {zip_name}")
    print(f"📏 EXE大小: {exe_size:.1f} MB")
    print(f"📏 ZIP大小: {zip_size:.1f} MB")
    print("\n📋 包含文件:")
    print("  - XexunRTT.exe (主程序)")
    print("  - README.md (使用说明)")
    print("  - ANTIVIRUS_INFO.md (防病毒说明)")
    print("  - 启动XexunRTT.bat (启动脚本)")
    print("\n💡 发布建议:")
    print("  1. 上传ZIP文件到发布平台")
    print("  2. 在发布说明中提及防病毒误报问题")
    print("  3. 提供ANTIVIRUS_INFO.md的内容作为说明")
    
    return True

if __name__ == '__main__':
    create_release_package()
