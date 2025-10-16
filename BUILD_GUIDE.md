# XexunRTT 构建指南

## 📋 快速开始

### 方式1: 使用一键构建脚本（推荐）

```bash
# Windows
build_release.bat

# Linux/macOS
bash build_release.sh
```

这个脚本会自动完成：
1. ✅ 更新翻译文件
2. ✅ 清理旧的构建文件
3. ✅ 构建可执行文件
4. ✅ 显示构建结果

### 方式2: 单独构建

```bash
# 只构建EXE（不更新翻译）
python build.py
```

### 方式3: 手动使用PyInstaller

```bash
# 手动构建（需要先运行build.py生成版本信息文件）
python build.py
# 或者直接使用PyInstaller
pyinstaller XexunRTT_onefile_v2_2.spec --clean
```

## 📝 版本管理

### 修改版本号

只需修改 `version.py` 文件中的 `VERSION` 常量：

```python
# version.py
VERSION = "2.3"  # 修改这里即可
```

所有相关文件会自动更新：
- EXE 文件名: `XexunRTT_v2.3.exe`
- 版本信息文件: `version_info_v2.3.txt`
- Windows 文件属性中的版本信息
- 关于对话框显示的版本号

### 版本信息内容

`version.py` 包含以下信息：
- `VERSION`: 版本号（如 "2.3"）
- `VERSION_NAME`: 应用名称
- `BUILD_TIME`: 构建时间（自动生成）
- `ABOUT_TEXT`: 关于对话框文本

## 🔧 构建系统说明

### 文件结构

```
RTT2UART2/
├── version.py                    # 版本信息（唯一的版本号来源）
├── build.py                      # 自动构建脚本
├── build_release.bat             # Windows 一键构建
├── build_release.sh              # Linux/macOS 一键构建
├── XexunRTT_onefile_v2_2.spec   # PyInstaller 配置文件
└── dist/
    └── XexunRTT_v2.3.exe        # 输出的可执行文件
```

### 构建流程

1. **读取版本号**: 从 `version.py` 读取 `VERSION` 和 `VERSION_NAME`
2. **生成版本信息文件**: 自动生成 `version_info_v{VERSION}.txt`
3. **更新spec文件**: 动态更新 `name` 和 `version` 参数
4. **运行PyInstaller**: 使用更新后的配置构建EXE
5. **输出结果**: 生成 `dist/XexunRTT_v{VERSION}.exe`

### 自动化特性

- ✅ **版本号统一**: 所有版本信息都从 `version.py` 读取
- ✅ **文件名动态**: EXE文件名自动包含版本号
- ✅ **版本信息自动生成**: Windows文件属性中的版本信息自动更新
- ✅ **翻译自动更新**: 一键脚本会先更新翻译文件
- ✅ **清理旧文件**: 构建前自动清理旧的构建产物

## 🚀 发布流程

### 1. 更新版本号

编辑 `version.py`:
```python
VERSION = "2.4"  # 新版本号
```

### 2. 运行一键构建

```bash
build_release.bat
```

### 3. 测试程序

```bash
dist\XexunRTT_v2.4.exe
```

### 4. 提交代码

```bash
git add .
git commit -m "release: v2.4"
git tag v2.4
git push origin master --tags
```

## 📚 翻译管理

### 更新翻译文件

```bash
# Windows
update_translations.bat

# Linux/macOS
bash update_translations.sh
```

翻译更新流程：
1. 提取所有可翻译字符串 (pyside6-lupdate)
2. 修复UI翻译 (fix_ui_translations.py)
3. 补全缺失翻译 (complete_all_translations.py 或 complete_all_missing_translations.py)
4. 编译翻译文件 (pyside6-lrelease)

## ⚙️ 高级配置

### 修改构建配置

编辑 `XexunRTT_onefile_v2_2.spec`:
- 添加/移除数据文件: `datas` 列表
- 添加/移除隐藏导入: `hiddenimports` 列表
- 排除模块: `excludes` 列表

### 优化构建大小

1. 检查 `excludes` 列表，排除不需要的模块
2. 使用 UPX 压缩（spec文件中 `upx=True`）
3. 移除不必要的数据文件

### 调试构建问题

```bash
# 查看详细日志
pyinstaller XexunRTT_onefile_v2_2.spec --clean --log-level DEBUG

# 查看警告信息
cat build/XexunRTT_onefile_v2_2/warn-XexunRTT_onefile_v2_2.txt
```

## 🐛 常见问题

### Q: 版本号显示不一致？
**A**: 确保 `version.py` 中的版本号是唯一的版本来源，不要在其他地方硬编码版本号。

### Q: 构建失败？
**A**: 检查：
1. Python 和 PyInstaller 是否正确安装
2. 所有依赖包是否已安装 (`pip install -r requirements.txt`)
3. 查看构建日志中的错误信息

### Q: 翻译文件更新失败？
**A**: 确保 PySide6 工具链已正确安装：
```bash
pip install PySide6
```

### Q: EXE运行时缺少文件？
**A**: 检查 `spec` 文件中的 `datas` 列表，确保所有必需的资源文件都被包含。

## 📞 技术支持

- 构建系统问题：查看 `build.py` 脚本中的错误输出
- 翻译问题：参考 `TRANSLATION_WORKFLOW.md`
- 编码规则：参考 `AI_CODING_RULES.md`

---

**最后更新**: 2025-10-16
**适用版本**: v2.3+

