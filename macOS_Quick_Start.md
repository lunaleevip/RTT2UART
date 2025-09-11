# 🍎 XexunRTT macOS 快速开始指南

## 🚀 一键构建

最简单的方式是使用构建启动器：

```bash
python build_macos_launcher.py
```

启动器会自动检测您的环境并推荐最佳构建方式。

## 📋 构建选项

### 选项 1：原生构建（在 macOS 上）
```bash
python build_macos.py
```
**优点：**
- ✅ 生成完整的 `.app` 应用程序包
- ✅ 自动创建 DMG 安装包
- ✅ 最佳兼容性和性能

### 选项 2：跨平台构建（任何系统）
```bash
python build_cross_platform.py
```
**适用于：**
- 🌍 Windows/Linux 开发者
- 📦 CI/CD 环境
- 🔄 批量构建

然后在 macOS 上完成最终打包：
```bash
./package_macos.sh
```

## 🛠️ 系统要求

- **macOS 10.13+** (High Sierra 或更高版本)
- **Python 3.8+**
- **J-Link 驱动程序**

## 📦 安装依赖

```bash
# 使用 macOS 优化的依赖
pip install -r requirements_macos.txt

# 或使用标准依赖
pip install -r requirements.txt
```

## 🎯 构建结果

### 原生构建输出
- `dist/XexunRTT.app` - 应用程序包
- `dist/XexunRTT_macOS_v1.0.5.dmg` - 安装包
- `dist/README_macOS.md` - 使用说明

### 跨平台构建输出
- `dist_macos/XexunRTT/` - 应用程序文件
- `package_macos.sh` - 最终打包脚本
- `macOS_Build_Guide.md` - 详细指南

## 🔒 安全设置

首次运行时，macOS 可能显示安全警告：

1. **右键点击** `XexunRTT.app`
2. 选择 **"打开"**
3. 在弹出对话框中点击 **"打开"**

或者在 **系统偏好设置 > 安全性与隐私 > 通用** 中允许应用运行。

## 🔌 J-Link 驱动

1. 访问 [SEGGER 官网](https://www.segger.com/downloads/jlink/)
2. 下载 **J-Link Software Pack for macOS**
3. 安装 DMG 包中的驱动程序
4. 重启 XexunRTT 应用程序

## 🎮 功能特性

- ✅ **RTT 查看器** - 实时查看 RTT 输出
- ✅ **多终端支持** - 支持多个 RTT 通道
- ✅ **串口转发** - RTT 数据转发到虚拟串口
- ✅ **ANSI 彩色** - 支持彩色文本显示
- ✅ **查找功能** - Ctrl+F 查找文本
- ✅ **深色模式** - 支持 macOS 深色主题

## 🛠️ 故障排除

### 无法打开应用程序
```
"XexunRTT.app" 已损坏，无法打开
```

**解决方案：**
```bash
# 移除隔离属性
sudo xattr -rd com.apple.quarantine /Applications/XexunRTT.app
```

### 无法连接 J-Link
1. 确认 J-Link 驱动已安装
2. 检查 USB 连接
3. 重新插拔设备
4. 检查是否被其他程序占用

### 应用崩溃
1. 检查 macOS 版本兼容性
2. 查看控制台日志：`Console.app`
3. 重新安装应用程序

## 📞 获取帮助

- **文档：** `README_macOS.md`
- **详细指南：** `macOS_Build_Guide.md`
- **问题反馈：** [GitHub Issues](https://github.com/xexun/RTT2UART)
- **技术支持：** support@xexun.com

## 🔗 相关链接

- **项目主页：** https://github.com/xexun/RTT2UART
- **SEGGER J-Link：** https://www.segger.com/products/debug-probes/j-link/
- **macOS 开发者文档：** https://developer.apple.com/documentation/

---

🎉 **祝您使用愉快！**

如果觉得有用，请给项目点个 ⭐ Star！
