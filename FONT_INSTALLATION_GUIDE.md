# 字体安装指南 - 获得完美的中英文等宽显示

## 🎯 问题说明

在显示中英文混合的日志时，需要使用**真正支持CJK（中日韩）的等宽字体**，确保：
- ✅ **中文字符宽度 = 2倍英文字符宽度**
- ✅ **完美对齐**：数字、英文大小写、标点符号都精确对齐
- ✅ **易于阅读**：清晰的字形设计，适合长时间阅读代码和日志

## 🏆 推荐字体：更纱黑体（Sarasa Gothic）

**更纱黑体**是专为编程和终端设计的开源字体，完美支持中英文等宽显示。

### Windows 安装步骤

#### 方法1：通过 Scoop 安装（推荐）

```powershell
# 1. 安装 Scoop（如果尚未安装）
iwr -useb get.scoop.sh | iex

# 2. 添加 nerd-fonts bucket
scoop bucket add nerd-fonts

# 3. 安装更纱黑体
scoop install sarasa-gothic

# 或者安装特定变体
scoop install Sarasa-Gothic-SC  # 简体中文版
```

#### 方法2：手动下载安装

1. **下载字体**
   - 官方GitHub：https://github.com/be5invis/Sarasa-Gothic/releases
   - 下载 `sarasa-gothic-ttf-<version>.7z`（~100MB）

2. **解压缩**
   - 使用 7-Zip 或 WinRAR 解压

3. **安装字体**
   - 找到 `sarasa-mono-sc-*.ttf` 文件（等宽版本）
   - 右键点击 → "为所有用户安装"（需要管理员权限）
   - 或批量选中多个字体文件 → 右键 → "安装"

4. **验证安装**
   - 打开 `控制面板` → `字体`
   - 搜索 "Sarasa" 或"更纱"
   - 应该看到多个 Sarasa Mono SC 字体

#### 方法3：通过 Chocolatey 安装

```powershell
choco install sarasa-gothic -y
```

### macOS 安装步骤

```bash
# 使用 Homebrew 安装
brew tap homebrew/cask-fonts
brew install font-sarasa-gothic

# 安装完成后，字体会自动可用
```

### Linux 安装步骤

```bash
# Ubuntu/Debian
sudo apt install fonts-sarasa-gothic

# Arch Linux
sudo pacman -S ttf-sarasa-gothic

# 或手动安装
wget https://github.com/be5invis/Sarasa-Gothic/releases/latest/download/sarasa-gothic-ttf.tar.bz2
tar -xjf sarasa-gothic-ttf.tar.bz2
mkdir -p ~/.fonts
cp sarasa-mono-sc-*.ttf ~/.fonts/
fc-cache -fv
```

## 📝 程序中使用

安装字体后：

1. **启动程序**
2. **在主界面找到 "字体" 下拉框**
3. **选择以下字体之一**：
   - `Sarasa Mono SC` （最佳选择）
   - `Sarasa Term SC`
   - `等距更纱黑体 SC`

4. **调整字体大小**（推荐9-11号）

配置会自动保存，下次启动时生效。

## 🎨 其他优秀的CJK等宽字体

如果无法安装更纱黑体，以下字体也支持良好的中英文等宽显示：

### Windows 自带
- **Cascadia Mono**（Windows 11自带，Windows 10需手动安装）
  - 下载：https://github.com/microsoft/cascadia-code/releases

### 开源字体
- **JetBrains Mono**
  - 下载：https://www.jetbrains.com/lp/mono/
  
- **Fira Code**
  - 下载：https://github.com/tonsky/FiraCode/releases

- **Source Code Pro**
  - 下载：https://github.com/adobe-fonts/source-code-pro/releases

### 商业字体（需购买）
- **Microsoft YaHei Mono**（微软雅黑等宽版）
- **Consolas + 微软雅黑**（混合方案）

## ❌ 不推荐的字体

以下字体**不支持**或**不完美支持**中英文等宽：

- ❌ `Consolas`：不支持中文，中文会使用后备字体，宽度不一致
- ❌ `Courier New`：中文显示效果差
- ❌ `Lucida Console`：同上
- ❌ `Monaco`：macOS字体，不支持中文

## 🔍 验证字体是否正确

安装字体后，在程序中查看以下内容是否完美对齐：

```
SIGNAL_QUALITY: RMS=0.800672
FFT_PEAK: 峰值=1.875 Hz
FFT_SPECTRUMS[19]: [6.21, 6.84, 7.47, 8.11, 8.74]
FFT_INTERP: Bin=5, Mag=14.49
```

**正确效果**：
- 所有数字、英文、冒号、等号应该完美垂直对齐
- 中文字符宽度 = 2个英文字符宽度
- 表格状的数据应该整齐排列

## 💡 故障排除

### 问题1：安装后在下拉框中找不到字体

**解决方法**：
1. 确认字体已正确安装（在系统字体文件夹中检查）
2. 重启程序
3. 检查日志中的 `[FONT] Available monospace fonts` 信息

### 问题2：中文仍然不对齐

**可能原因**：
- 字体名称选择错误（应选 `Sarasa Mono` 而非 `Sarasa Gothic`）
- 字体安装不完整
- 需要重启程序或系统

**解决方法**：
1. 确认选择的是 `Mono` 变体（等宽版本）
2. 重新安装字体
3. 重启计算机

### 问题3：字体看起来模糊

**解决方法**：
1. 调整字体大小（推荐9-11号）
2. 检查系统DPI设置
3. 在高分辨率屏幕上使用更大的字号

## 📚 参考资源

- [更纱黑体官方仓库](https://github.com/be5invis/Sarasa-Gothic)
- [等宽字体比较网站](https://www.programmingfonts.org/)
- [CJK字体测试页面](https://github.com/be5invis/Sarasa-Gothic/blob/master/doc/charsets.md)

## ✅ 推荐配置

**最佳配置**：
- 字体：`Sarasa Mono SC`
- 大小：`9-11`（根据屏幕分辨率调整）
- 行距：默认

这样可以获得最清晰、最整齐的日志显示效果！🎉

