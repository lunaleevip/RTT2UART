# Qt 繁体中文翻译文件添加说明

## ✅ **完成内容**

已成功添加 Qt 自带的繁体中文翻译文件！

---

## 🎯 **问题背景**

之前只添加了应用程序的繁体翻译（`xexunrtt_zh_TW.qm`），但 **Qt 框架自带的对话框和控件**（如 QMessageBox、QFileDialog、QPushButton 等）仍然显示简体中文或英文。

---

## 📁 **新增文件**

| 文件 | 说明 | 大小 |
|-----|------|------|
| `qt_zh_TW.qm` | Qt 框架繁体中文翻译文件 | 126,185 字节 |

**来源**：从 PySide6 安装目录复制
```
C:\Users\[用户]\AppData\Local\Programs\Python\Python313\Lib\site-packages\PySide6\translations\qtbase_zh_TW.qm
```

---

## 🔄 **翻译文件对照**

### 简体中文（zh_CN）

| 类型 | 文件 | 大小 | 说明 |
|-----|------|------|------|
| 应用翻译 | `xexunrtt_complete.qm` | 30,493 字节 | 应用程序界面翻译 |
| Qt 翻译 | `qt_zh_CN.qm` | 136,673 字节 | Qt 框架翻译 |

### 繁体中文（zh_TW）

| 类型 | 文件 | 大小 | 说明 |
|-----|------|------|------|
| 应用翻译 | `xexunrtt_zh_TW.qm` | 30,588 字节 | 应用程序界面翻译 |
| Qt 翻译 | `qt_zh_TW.qm` | 126,185 字节 | Qt 框架翻译 ✨ **新增** |

---

## 🛠️ **代码修改**

### 1. `main_window.py`

#### 修改前（简繁共用）

```python
if config_language in ['zh_CN', 'zh_TW']:
    # 简体和繁体都使用 qt_zh_CN.qm
    qt_qm_paths = [
        get_resource_path("qt_zh_CN.qm"),
        "qt_zh_CN.qm",
    ]
```

#### 修改后（独立加载）

```python
if config_language in ['zh_CN', 'zh_TW']:
    # 根据语言选择对应的Qt翻译文件
    qt_translation_file = "qt_zh_CN.qm" if config_language == 'zh_CN' else "qt_zh_TW.qm"
    
    qt_qm_paths = [
        get_resource_path(qt_translation_file),
        qt_translation_file,
        f"../Resources/{qt_translation_file}",
        f":/{qt_translation_file}"
    ]
```

### 2. `XexunRTT_onefile_v2_2.spec`

#### 修改前

```python
datas=[
    ('xexunrtt_complete.qm', '.'),
    ('qt_zh_CN.qm', '.'),
    ('JLinkDevicesBuildIn.xml', '.'),
],
```

#### 修改后

```python
datas=[
    ('xexunrtt_complete.qm', '.'),     # 简体中文应用翻译
    ('xexunrtt_zh_TW.qm', '.'),        # 繁体中文应用翻译
    ('qt_zh_CN.qm', '.'),              # Qt 简体中文翻译
    ('qt_zh_TW.qm', '.'),              # Qt 繁体中文翻译 ✨ 新增
    ('JLinkDevicesBuildIn.xml', '.'),
],
```

---

## 🌍 **翻译覆盖范围**

### 应用程序翻译（xexunrtt_*.qm）

负责翻译：
- ✅ 菜单栏（连接、窗口、工具、帮助）
- ✅ 按钮文字（连接、断开连接、重新连接）
- ✅ 标签文字（JLink调试日志、设备列表）
- ✅ 提示信息（Tooltip）
- ✅ 状态栏信息
- ✅ 自定义对话框内容

### Qt 框架翻译（qt_*.qm）

负责翻译：
- ✅ **QMessageBox**（确定、取消、是、否、关闭）
- ✅ **QFileDialog**（打开、保存、文件名、类型）
- ✅ **QInputDialog**（确定、取消）
- ✅ **QPushButton** 默认文字
- ✅ **QDialogButtonBox** 标准按钮
- ✅ **快捷键提示**（Ctrl+C、Ctrl+V）
- ✅ **上下文菜单**（复制、粘贴、剪切）

---

## 📊 **翻译效果对比**

### 示例 1：QMessageBox

#### 简体中文（zh_CN）
```
标题：语言
内容：语言已切换到中文（简体）
      请重启应用程序使更改生效。
按钮：[确定]
```

#### 繁体中文（zh_TW）
```
標題：語言
內容：語言已切換到中文（繁體）
      請重啟應用程式使更改生效。
按鈕：[確定]  ← Qt 翻译
```

### 示例 2：QFileDialog

#### 简体中文（zh_CN）
```
标题：打开文件
文件名：____________
文件类型：所有文件 (*.*)
按钮：[打开] [取消]
```

#### 繁体中文（zh_TW）
```
標題：打開檔案      ← Qt 翻译
檔案名稱：____________  ← Qt 翻译
檔案類型：所有檔案 (*.*)  ← Qt 翻译
按鈕：[打開] [取消]    ← Qt 翻译
```

---

## 🧪 **测试步骤**

### 1. 测试应用翻译

```bash
python -c "from PySide6.QtCore import QTranslator, QCoreApplication; from PySide6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); t = QTranslator(); t.load('xexunrtt_zh_TW.qm'); QCoreApplication.installTranslator(t); print(QCoreApplication.translate('main_window', 'JLink Debug Log'))"
```

预期输出：`JLink調試日誌`

### 2. 测试 Qt 翻译

```bash
python -c "from PySide6.QtCore import QTranslator, QCoreApplication; from PySide6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); t = QTranslator(); t.load('qt_zh_TW.qm'); QCoreApplication.installTranslator(t); print(QCoreApplication.translate('QPlatformTheme', 'OK'))"
```

预期输出：`確定`

### 3. 完整测试

```bash
# 设置为繁体中文
python -c "from config_manager import config_manager; config_manager.set_language('zh_TW'); config_manager.save_config()"

# 启动程序
python main_window.py
```

**检查点**：
- ✅ 菜单栏显示繁体（連接、窗口、工具、幫助）
- ✅ 消息框按钮显示繁体（確定、取消）
- ✅ 文件对话框显示繁体（打開、儲存、檔案）
- ✅ 右键菜单显示繁体（複製、貼上、剪下）

---

## 🔧 **获取 Qt 翻译文件的方法**

### 方法 1：从 PySide6 安装目录复制（推荐）

```python
import PySide6
import os
import shutil

qt_dir = os.path.join(os.path.dirname(PySide6.__file__), 'translations')
src = os.path.join(qt_dir, 'qtbase_zh_TW.qm')
dst = 'qt_zh_TW.qm'
shutil.copy2(src, dst)
print(f'Copied: {dst}')
```

### 方法 2：查找所有可用的 Qt 翻译

```python
import PySide6
import os
import glob

qt_dir = os.path.join(os.path.dirname(PySide6.__file__), 'translations')
files = glob.glob(os.path.join(qt_dir, '*_zh_TW.qm'))

for f in files:
    print(os.path.basename(f))
```

**输出示例**：
```
qtbase_zh_TW.qm          ← 核心翻译（必需）
qtdeclarative_zh_TW.qm   ← QML 翻译
qtmultimedia_zh_TW.qm    ← 多媒体翻译
qt_help_zh_TW.qm         ← 帮助系统翻译
qt_zh_TW.qm              ← 旧版通用翻译（99B，不推荐）
```

**推荐使用**：`qtbase_zh_TW.qm` → 重命名为 `qt_zh_TW.qm`

---

## 📦 **打包注意事项**

### PyInstaller 配置

确保 `.spec` 文件包含所有翻译文件：

```python
datas=[
    # 应用翻译
    ('xexunrtt_complete.qm', '.'),     # 简体
    ('xexunrtt_zh_TW.qm', '.'),        # 繁体
    
    # Qt 翻译
    ('qt_zh_CN.qm', '.'),              # 简体
    ('qt_zh_TW.qm', '.'),              # 繁体
    
    # 其他资源
    ('JLinkDevicesBuildIn.xml', '.'),
]
```

### macOS 打包

将翻译文件复制到 Resources 目录：

```bash
cp xexunrtt_complete.qm XexunRTT.app/Contents/Resources/
cp xexunrtt_zh_TW.qm XexunRTT.app/Contents/Resources/
cp qt_zh_CN.qm XexunRTT.app/Contents/Resources/
cp qt_zh_TW.qm XexunRTT.app/Contents/Resources/
```

---

## 🌐 **完整的语言支持**

| 语言 | 应用翻译 | Qt 翻译 | 状态 |
|-----|---------|---------|------|
| English | - | - | ✅ 原生支持 |
| 简体中文 | `xexunrtt_complete.qm` | `qt_zh_CN.qm` | ✅ 完整支持 |
| 繁体中文 | `xexunrtt_zh_TW.qm` | `qt_zh_TW.qm` | ✅ **完整支持** ✨ |

---

## 🐛 **已知问题**

### 1. 终端输出乱码

**问题**：Windows 终端显示中文为乱码

```
Qt translation: �_��
```

**原因**：Windows 终端默认 GBK 编码

**影响**：仅终端输出，实际程序界面显示正常

**解决**：无需解决，不影响使用

### 2. 文件大小差异

**问题**：`qt_zh_TW.qm` (126KB) 比 `qt_zh_CN.qm` (136KB) 小

**原因**：不同 Qt 版本或翻译覆盖范围不同

**影响**：无影响，核心功能都已翻译

---

## 🔄 **更新流程**

当 Qt 版本更新时，可能需要更新翻译文件：

### 1. 检查 Qt 版本

```bash
python -c "import PySide6; print(PySide6.__version__)"
```

### 2. 复制新的翻译文件

```bash
# 简体
python -c "import PySide6; import os; import shutil; qt_dir = os.path.join(os.path.dirname(PySide6.__file__), 'translations'); shutil.copy2(os.path.join(qt_dir, 'qtbase_zh_CN.qm'), 'qt_zh_CN.qm')"

# 繁体
python -c "import PySide6; import os; import shutil; qt_dir = os.path.join(os.path.dirname(PySide6.__file__), 'translations'); shutil.copy2(os.path.join(qt_dir, 'qtbase_zh_TW.qm'), 'qt_zh_TW.qm')"
```

### 3. 测试

```bash
python main_window.py
```

---

## 📝 **简繁对照（Qt 控件）**

| 简体 | 繁体 | 控件 |
|-----|------|------|
| 确定 | 確定 | QMessageBox, QDialogButtonBox |
| 取消 | 取消 | QMessageBox, QDialogButtonBox |
| 是 | 是 | QMessageBox |
| 否 | 否 | QMessageBox |
| 打开 | 打開 | QFileDialog |
| 保存 | 儲存 | QFileDialog |
| 文件名 | 檔案名稱 | QFileDialog |
| 文件类型 | 檔案類型 | QFileDialog |
| 所有文件 | 所有檔案 | QFileDialog |
| 复制 | 複製 | 右键菜单 |
| 粘贴 | 貼上 | 右键菜单 |
| 剪切 | 剪下 | 右键菜单 |
| 全选 | 全選 | 右键菜单 |
| 删除 | 刪除 | 右键菜单 |

---

## ✅ **完成清单**

- [x] 从 PySide6 安装目录复制 `qtbase_zh_TW.qm`
- [x] 重命名为 `qt_zh_TW.qm`
- [x] 修改 `main_window.py` 加载逻辑
- [x] 更新 `XexunRTT_onefile_v2_2.spec` 打包配置
- [x] 测试应用翻译
- [x] 测试 Qt 翻译
- [x] 验证消息框按钮
- [x] 验证文件对话框
- [x] 提交代码到 Git
- [x] 创建文档说明

---

## 🎉 **总结**

**现在支持完整的繁体中文翻译！**

包括：
- ✅ 应用程序界面（菜单、按钮、标签）
- ✅ Qt 框架控件（对话框、按钮、菜单）

用户切换到繁体中文后，整个程序界面（包括系统对话框）都会显示正确的繁体中文！

---

## 🚀 **使用方法**

### 切换到繁体中文

```bash
# 方法1：通过 Language 菜单
Language → 中文（繁體） → 確定 → 重启

# 方法2：命令行
python -c "from config_manager import config_manager; config_manager.set_language('zh_TW'); config_manager.save_config()"
python main_window.py
```

现在，不仅程序界面是繁体，连 **"确定"、"取消"** 这些系统按钮也会显示为 **"確定"、"取消"** 了！🎊

---

## 📚 **相关文档**

- `繁体中文翻译添加说明.md` - 应用翻译说明
- `语言设置功能说明.md` - 语言设置功能详细说明
- `convert_to_traditional.py` - 简繁转换脚本

---

## 💡 **技术细节**

### Qt 翻译文件命名规则

| 文件 | 说明 |
|-----|------|
| `qtbase_*.qm` | Qt 核心模块翻译（QtCore, QtGui, QtWidgets） |
| `qtdeclarative_*.qm` | QML/Qt Quick 翻译 |
| `qtmultimedia_*.qm` | 多媒体模块翻译 |
| `qt_help_*.qm` | 帮助系统翻译 |
| `qt_*.qm` | 旧版通用翻译（已弃用） |

**推荐**：使用 `qtbase_*.qm` 并重命名为 `qt_*.qm`

### 加载顺序

```python
# 1. 加载应用翻译
app_translator = QTranslator()
app_translator.load('xexunrtt_zh_TW.qm')
QCoreApplication.installTranslator(app_translator)

# 2. 加载 Qt 翻译
qt_translator = QTranslator()
qt_translator.load('qt_zh_TW.qm')
QCoreApplication.installTranslator(qt_translator)  # 后加载，优先级低
```

**注意**：应用翻译的优先级高于 Qt 翻译。

---

🎊 **繁体中文翻译完全支持已完成！**

