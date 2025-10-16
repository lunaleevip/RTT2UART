# AI Coding Rules for XexunRTT Project

## 1. 核心原则
- **代码标识符必须使用英文**：类名、方法名、变量名都用英文
- **代码注释使用中文**：所有注释必须用中文，便于中文开发者理解
- **不要使用EMOJI表情**：代码中不得使用任何EMOJI表情符号（🔧📋💾等），发现的需要修复
- **不要硬编码中文字符串**：用户界面文本使用`QCoreApplication.translate()`，硬编码英文，通过`.ts`/`.qm`翻译文件提供多语言
- **日志输出必须使用translate**：所有日志消息也必须通过translate系统处理，确保可翻译
- **修改代码后不要主动提交或编译**，只提出建议等待用户批准
- **Windows PowerShell环境**：AI运行在Windows PowerShell环境，必须正确处理UTF-8编码，避免中文乱码
- **详细规则见项目根目录的 AI_CODING_RULES.md 文件**

## 📝 代码注释规范

### 注释规则
所有代码注释都必须使用**中文**，保持一致性和可读性。

#### ✅ 正确示例
```python
# 获取系统DPI缩放比例
def get_system_dpi():
    """获取系统DPI缩放比例"""
    try:
        if sys.platform == "darwin":  # macOS系统
            # 使用Qt获取屏幕DPI
            app = QApplication.instance()
            # 计算缩放比例
            scale_factor = device_pixel_ratio
            return scale_factor
```

#### ❌ 错误示例
```python
# Get system DPI scale factor (❌ 不要用英文注释)
def get_system_dpi():
    try:
        if sys.platform == "darwin":  # macOS (❌ 混合中英注释)
            # Use Qt to get screen DPI (❌ 英文注释)
            app = QApplication.instance()
```

### 注释类型

#### 1. 行内注释（单行注释）
```python
# 清空缓冲区数据
buffer.clear()

# 检查是否为None
if obj is None:  # 空值检查
    pass
```

#### 2. 多行注释（块注释）
```python
# 修复Python控制台编码问题
# 确保UTF-8输出正常显示
# 防止中文乱码
def fix_console_encoding():
    pass
```

#### 3. 函数/类文档字符串
```python
def calculate_buffer_size(data_count):
    """
    计算缓冲区大小
    
    Args:
        data_count: 数据项数量
    
    Returns:
        计算得出的缓冲区大小（字节）
    """
    pass

class RTTWorker(QObject):
    """
    RTT2UART工作线程类
    
    负责处理RTT数据读取和日志写入
    """
    pass
```

#### 4. TODO/FIXME注释
```python
# TODO: 优化缓冲区管理，减少内存占用
# FIXME: 修复某些情况下的乱码问题
# NOTE: 这里使用特殊处理是为了兼容旧版本
```

## 🚫 禁止使用的内容

### 1. 禁止使用EMOJI表情符号

**规则**：代码中任何地方都不得使用EMOJI表情符号。

#### ❌ 错误示例
```python
# 日志输出中使用EMOJI
logger.info("🪟 Window initialized with ID: %s", window_id)
logger.debug("📋 命令历史已同步到settings: %d 条", count)
logger.info("🎯 Current DPI scale: %.2f", scale)

# print语句中使用EMOJI
print("✅ 中文翻译加载成功")
print("🔍 添加设备到ComboBox")
print("⚠️ 选择了空项或无效索引")

# UI文本中使用EMOJI
self.status_label.setText("💾 保存成功")
```

#### ✅ 正确示例
```python
# 使用纯文本描述
logger.info("Window initialized with ID: %s", window_id)
logger.debug("命令历史已同步到settings: %d 条", count)
logger.info("Current DPI scale: %.2f", scale)

# print语句使用纯文本
print("✓ 中文翻译加载成功")  # 使用ASCII字符代替
print("添加设备到ComboBox")
print("警告: 选择了空项或无效索引")

# UI文本使用纯文本
self.status_label.setText(QCoreApplication.translate("MainWindow", "Save successful"))
```

**原因**：
- EMOJI在不同操作系统、终端、编辑器中显示不一致
- 可能导致编码问题和日志解析困难
- 影响专业性和可维护性
- 在某些环境下可能显示为乱码或方框

### 2. 禁止硬编码中文字符串

**规则**：所有用户可见的文本必须通过`QCoreApplication.translate()`处理，不得在代码中直接硬编码中文。

#### ❌ 错误示例
```python
# UI元素硬编码中文
button = QPushButton("查找")
label = QLabel("查找内容:")
combo.addItem("自动检测")

# 对话框硬编码中文
QMessageBox.information(self, "提示", "操作成功")

# print输出硬编码中文
print("配置文件加载成功")

# 日志输出硬编码中文
logger.info("设备连接确认: %s", device)
```

#### ✅ 正确示例
```python
# UI元素使用translate
button = QPushButton(QCoreApplication.translate("ClassName", "Find"))
label = QLabel(QCoreApplication.translate("ClassName", "Find:"))
combo.addItem(QCoreApplication.translate("ClassName", "Auto Detect"))

# 对话框使用translate
QMessageBox.information(
    self,
    QCoreApplication.translate("ClassName", "Info"),
    QCoreApplication.translate("ClassName", "Operation successful")
)

# print输出使用translate
print(QCoreApplication.translate("main", "Config file loaded successfully"))

# 日志输出使用translate
logger.info(QCoreApplication.translate("main", "Device connection confirmed: %s"), device)
```

**原因**：
- 支持多语言切换
- 便于维护和更新翻译
- 符合国际化标准
- 便于用户自定义语言

### 3. 注释必须使用中文

**规则**：所有代码注释都必须使用中文，包括单行注释、多行注释、文档字符串。

#### ❌ 错误示例
```python
# Initialize the buffer (错误：英文注释)
def init_buffer():
    """
    Initialize the data buffer
    
    Args:
        size: Buffer size in bytes
    
    Returns:
        Initialized buffer object
    """
    # Allocate memory (错误：英文注释)
    buffer = bytearray(size)
    return buffer

# Mix of Chinese and English (错误：混合注释)
def process_data():
    # 处理数据
    data = get_data()  # Get raw data (错误：混合)
    return data
```

#### ✅ 正确示例
```python
# 初始化缓冲区
def init_buffer():
    """
    初始化数据缓冲区
    
    Args:
        size: 缓冲区大小（字节）
    
    Returns:
        已初始化的缓冲区对象
    """
    # 分配内存
    buffer = bytearray(size)
    return buffer

# 完全使用中文注释
def process_data():
    # 处理数据
    data = get_data()  # 获取原始数据
    return data
```

**原因**：
- 本项目主要面向中文开发者
- 提高代码可读性和维护性
- 保持注释风格一致性
- 便于团队协作

### 发现违规代码时的处理

当发现代码中存在以上违规内容时：

1. **EMOJI表情**：
   - 直接删除或替换为ASCII字符（如 ✓、×、!、>）
   - 或完全使用文字描述

2. **硬编码中文**：
   - 改用`QCoreApplication.translate()`包装
   - 在`.ts`文件中添加对应翻译

3. **英文注释**：
   - 直接翻译为中文
   - 保持注释的准确性和完整性

## 📝 Translation System

### Translation File Format
- Use Qt Linguist format: `.ts` (source) and `.qm` (compiled)
- Translation file: `xexunrtt_complete.ts` → `xexunrtt_complete.qm`
- Qt translation file: `qt_zh_CN.qm` for Qt built-in widgets

### How to Add Translatable Text

**Bad Example:**
```python
button = QPushButton("查找")  # ❌ Hard-coded Chinese
label.setText("查找内容:")     # ❌ Hard-coded Chinese
```

**Good Example:**
```python
button = QPushButton(QCoreApplication.translate("ClassName", "Find"))
label.setText(QCoreApplication.translate("ClassName", "Find:"))
```

### Context Names
- Use the **class name** as the translation context (first parameter)
- Examples:
  - `FindDialog` for FindDialog class texts
  - `FindAllResultsWindow` for FindAllResultsWindow class texts
  - `main_window` for main window texts

### Translation Workflow
1. Write code with English text using `QCoreApplication.translate()`
2. Run `pyside6-lupdate` to extract strings to `.ts` file
   - **CRITICAL**: Include ALL source files: `.py` AND `.ui` files
   - Correct command: `pyside6-lupdate main_window.py xexunrtt.ui rtt2uart.ui sel_device.ui -ts xexunrtt_complete.ts`
   - If you only include `.py` files, translations from `.ui` files will be marked as `type="vanished"` and lost!
3. **IMPORTANT**: Use Python script or Qt Linguist to edit `.ts` file, **NEVER manually edit with text editor** to avoid encoding issues
4. Run `pyside6-lrelease` to compile `.ts` to `.qm` file
5. Deploy `.qm` file with application

### ⚠️ Critical: Avoid Manual Editing of .ts Files
**Problem**: Manually editing `.ts` files with text editors can cause:
- UTF-8 encoding corruption
- Chinese characters truncated or garbled
- Breaking translations in other contexts

**Solution**: Always use one of these methods:
1. **Qt Linguist** (Recommended): GUI tool for translation
2. **Python script**: Use `xml.etree.ElementTree` with explicit UTF-8 encoding
3. **Never use**: Search/replace in text editors like VSCode, Notepad++, etc.

**Correct Python Script Template**:
```python
import xml.etree.ElementTree as ET

def update_translations(ts_file):
    tree = ET.parse(ts_file, parser=ET.XMLParser(encoding='utf-8'))
    root = tree.getroot()
    
    # ... modify translations ...
    
    tree.write(ts_file, encoding='utf-8', xml_declaration=True)
```

## ⚠️ COMMON MISTAKES & HOW TO AVOID THEM

### Mistake #1: 手动编辑 .ts 文件导致乱码
**错误现象**：
- 中文字符被截断，如 "区分大小写" 变成 "区分大小�?"
- 翻译文件编码损坏
- 其他翻译也受影响

**原因**：
使用文本编辑器（VSCode、Notepad++等）的 search/replace 功能直接修改 .ts 文件时，编码处理不当。

**预防方法**：
```python
# ❌ 错误：不要这样做
# 在编辑器中直接查找替换 .ts 文件

# ✅ 正确：使用 Python 脚本
import xml.etree.ElementTree as ET

tree = ET.parse('xexunrtt_complete.ts', parser=ET.XMLParser(encoding='utf-8'))
# ... 修改 ...
tree.write('xexunrtt_complete.ts', encoding='utf-8', xml_declaration=True)
```

### Mistake #2: 提取翻译时漏掉 .ui 文件
**错误现象**：
- 对话框界面显示英文
- .ts 文件中原有翻译被标记为 `type="vanished"`
- 编译后的 .qm 文件缺少部分翻译

**原因**：
运行 `pyside6-lupdate` 时只包含了 .py 文件，没有包含所有 .ui 文件。

**预防方法**：
```powershell
# ❌ 错误：只包含 .py 文件
pyside6-lupdate main_window.py -ts xexunrtt_complete.ts

# ✅ 正确：包含所有源文件（ALL .py and ALL .ui files）
pyside6-lupdate main_window.py xexunrtt.ui rtt2uart.ui rtt2uart_updated.ui sel_device.ui -ts xexunrtt_complete.ts
```

**检查方法**：
```powershell
# 检查所有 .ui 文件
dir *.ui

# 确保都包含在 lupdate 命令中
```

### Mistake #3: 更新翻译后忘记编译 .qm 文件
**错误现象**：
- .ts 文件已更新，但程序界面没有变化
- 修改的翻译不生效

**原因**：
只修改了 .ts 源文件，但没有编译成 .qm 二进制文件。程序运行时加载的是 .qm 文件。

**预防方法**：
```powershell
# 完整的翻译更新流程
# 1. 提取字符串
pyside6-lupdate main_window.py xexunrtt.ui rtt2uart.ui rtt2uart_updated.ui sel_device.ui -ts xexunrtt_complete.ts

# 2. 编辑翻译（使用 Qt Linguist 或 Python 脚本）
python update_translations.py

# 3. ⚠️ 必须编译 .qm 文件
pyside6-lrelease xexunrtt_complete.ts

# 4. 测试程序
python main_window.py
```

### Mistake #4: 使用错误的命令名
**错误现象**：
- 命令未找到错误
- 翻译文件无法更新或编译

**原因**：
混淆了不同的命令名称。

**正确命令对照表**：
| 功能 | ✅ 正确命令 | ❌ 错误命令 |
|------|-----------|----------|
| 提取翻译 | `pyside6-lupdate` | `pylupdate6`, `lupdate` |
| 编译翻译 | `pyside6-lrelease` | `pylrc`, `lrelease` |
| UI转Python | `pyside6-uic` | `pyuic6`, `uic` |

### Mistake #5: 翻译上下文名称不一致
**错误现象**：
- 翻译无法应用到界面元素
- 同样的英文在不同地方显示不同

**原因**：
`QCoreApplication.translate()` 的第一个参数（context）与 .ts 文件中的 context 名称不匹配。

**预防方法**：
```python
# ✅ 正确：使用类名作为 context
class FindDialog(QDialog):
    def __init__(self):
        self.setWindowTitle(QCoreApplication.translate("FindDialog", "Find"))
        #                                              ^^^^^^^^^^^^ 
        #                                              必须与类名一致

# ❌ 错误：context 名称随意
QCoreApplication.translate("MyDialog", "Find")  # context 不存在
```

### Mistake #6: 遗漏新添加的 UI 文件
**错误现象**：
- 新添加的对话框没有翻译
- 部分界面元素显示英文

**原因**：
项目中添加了新的 .ui 文件，但 lupdate 命令中没有包含。

**预防方法**：
```powershell
# 定期检查所有 .ui 文件
Get-ChildItem -Filter *.ui | Select-Object Name

# 更新 lupdate 命令，确保包含所有文件
# 当前项目的所有 .ui 文件：
# - xexunrtt.ui
# - rtt2uart.ui
# - rtt2uart_updated.ui
# - sel_device.ui
```

### Mistake #7: 代码中使用EMOJI表情符号
**错误现象**：
- 终端日志显示EMOJI：🪟🖥️🎯📏📋💾🚨✅❌⚠️🔧📊
- print输出包含EMOJI
- 在某些环境下显示为方框或乱码

**原因**：
在日志输出、print语句、UI文本中直接使用了EMOJI字符。

**预防方法**：
```python
# ❌ 错误：使用EMOJI
logger.info("🪟 Window initialized")
print("✅ 翻译加载成功")
logger.debug("📋 命令历史已同步")

# ✅ 正确：使用纯文本
logger.info("Window initialized")
print("翻译加载成功")
logger.debug("命令历史已同步")

# ✅ 或使用ASCII符号
print("✓ 翻译加载成功")  # 使用 ✓ 代替 ✅
logger.warning("! 选择了空项或无效索引")  # 使用 ! 代替 ⚠️
```

**修复方法**：
```python
# 使用grep查找所有EMOJI
import re
emoji_pattern = re.compile("[\U0001F300-\U0001F9FF]")

# 手动搜索和替换，逐个修复
```

### Mistake #8: 硬编码中文字符串
**错误现象**：
- UI界面无法切换语言
- print输出直接显示中文
- 日志消息硬编码中文

**原因**：
未使用`QCoreApplication.translate()`处理用户可见文本。

**预防方法**：
```python
# ❌ 错误：硬编码中文
button = QPushButton("确定")
print("配置文件加载成功")
logger.info("设备连接确认: %s", device)

# ✅ 正确：使用translate
button = QPushButton(QCoreApplication.translate("ClassName", "OK"))
print(QCoreApplication.translate("main", "Config file loaded successfully"))
logger.info(QCoreApplication.translate("main", "Device connection confirmed: %s"), device)
```

**检查方法**：
```python
# 查找硬编码中文（使用grep）
# 搜索pattern: ["\'][\u4e00-\u9fff]+["\']
# 排除注释行（# 开头）
```

### Mistake #9: 添加新UI元素后未提取和翻译
**错误现象**：
- 新添加的按钮、标签、下拉框等显示英文
- .ui 文件中的新文本没有中文翻译
- 用户界面部分显示英文，部分显示中文

**原因**：
在 .ui 文件中添加了新的UI元素（使用Qt Designer），但忘记重新提取翻译。

**完整的 UI 修改流程**：
```powershell
# 1. 使用 Qt Designer 修改 .ui 文件（添加/修改UI元素）
# 2. 重新提取所有翻译（包含所有 .py 和 .ui 文件）
pyside6-lupdate main_window.py xexunrtt.ui rtt2uart.ui rtt2uart_updated.ui sel_device.ui -ts xexunrtt_complete.ts -noobsolete

# 3. 检查哪些翻译缺失
python check_missing_translations.py

# 4. 使用 Python 脚本添加中文翻译
python update_translations.py

# 5. 编译 .qm 文件
pyside6-lrelease xexunrtt_complete.ts

# 6. 测试程序，检查所有UI元素是否正确翻译
python main_window.py
```

**检查翻译完整性的脚本模板**：
```python
import xml.etree.ElementTree as ET

parser = ET.XMLParser(encoding='utf-8')
tree = ET.parse('xexunrtt_complete.ts', parser=parser)
root = tree.getroot()

missing = []
for context_elem in root.findall('context'):
    context_name = context_elem.find('name').text
    for message_elem in context_elem.findall('message'):
        source = message_elem.find('source').text
        translation = message_elem.find('translation')
        if translation is None or not translation.text or translation.get('type') == 'unfinished':
            missing.append((context_name, source))

if missing:
    print(f"⚠️  Found {len(missing)} missing translations!")
    for ctx, src in missing:
        print(f"  [{ctx}] {src}")
else:
    print("✅ All translations complete!")
```

## 🔧 Code Quality Checklist

在修改代码时，按此清单检查：

### 代码风格检查
- [ ] 1. 所有注释都使用中文
- [ ] 2. 代码中没有EMOJI表情符号
- [ ] 3. 没有硬编码的中文字符串（使用translate）
- [ ] 4. 所有标识符使用英文命名

### 翻译检查
- [ ] 5. 确认所有 .ui 文件都包含在 `pyside6-lupdate` 命令中
- [ ] 6. 使用 Python 脚本或 Qt Linguist 编辑 .ts 文件（不要手动编辑）
- [ ] 7. 运行 `pyside6-lrelease` 编译 .qm 文件
- [ ] 8. 测试程序，检查所有界面翻译是否正确
- [ ] 9. 检查是否有 `type="vanished"` 的翻译（如果有，说明漏了某些源文件）
- [ ] 10. 提交时包含 .ts 和 .qm 两个文件

## 🚨 Emergency Fix: 翻译损坏了怎么办？

如果翻译文件损坏：

```powershell
# 1. 恢复到上次正确的版本
git checkout xexunrtt_complete.ts xexunrtt_complete.qm

# 2. 重新提取所有翻译（包含所有源文件）
pyside6-lupdate main_window.py xexunrtt.ui rtt2uart.ui rtt2uart_updated.ui sel_device.ui -ts xexunrtt_complete.ts

# 3. 使用 Python 脚本更新新的翻译
# （不要手动编辑！）
python update_translations.py

# 4. 编译
pyside6-lrelease xexunrtt_complete.ts

# 5. 测试
python main_window.py
```

### Common Translation Patterns

#### Dialogs
```python
self.setWindowTitle(QCoreApplication.translate("DialogName", "Dialog Title"))
```

#### Labels
```python
label = QLabel(QCoreApplication.translate("ClassName", "Label Text:"))
```

#### Buttons
```python
btn = QPushButton(QCoreApplication.translate("ClassName", "Button Text"))
```

#### Checkboxes
```python
checkbox = QCheckBox(QCoreApplication.translate("ClassName", "Option Name"))
```

#### Placeholders
```python
line_edit.setPlaceholderText(QCoreApplication.translate("ClassName", "Enter text..."))
```

#### Combo Box Items
```python
combo.addItem(QCoreApplication.translate("ClassName", "Item Text"))
```

#### Messages
```python
QMessageBox.information(
    self,
    QCoreApplication.translate("ClassName", "Title"),
    QCoreApplication.translate("ClassName", "Message text")
)
```

#### Dynamic Text with Parameters
```python
# Use .format() for parameters
text = QCoreApplication.translate("ClassName", "Found {0} results").format(count)

# For Qt Linguist, the .ts file will contain:
# <message>
#     <source>Found {0} results</source>
#     <translation>找到 {0} 个结果</translation>
# </message>
```

## 🔧 Development Workflow Rules

### When Making Code Changes

1. **Write English Code First**
   - Use English for all identifiers
   - Use `QCoreApplication.translate()` for UI text

2. **Do Not Auto-update Translations**
   - Only propose `pylupdate6` commands
   - Wait for user to approve

3. **Do Not Auto-commit**
   - Only propose git commands
   - Wait for user to approve

4. **Do Not Auto-compile**
   - Only propose build commands
   - Wait for user to approve

### Example Workflow

```python
# Step 1: Write code with English
class FindDialog(QDialog):
    def __init__(self):
        self.setWindowTitle(QCoreApplication.translate("FindDialog", "Find"))
        self.find_btn = QPushButton(QCoreApplication.translate("FindDialog", "Find Next"))

# Step 2: Propose translation update (DO NOT RUN)
# Propose: pylupdate6 main_window.py -ts xexunrtt_complete.ts

# Step 3: User manually translates or approves

# Step 4: Propose translation compile (DO NOT RUN)
# Propose: pylrc xexunrtt_complete.ts
```

## 📚 Configuration Management

### Search History
- Save search history using `config_manager`
- Maximum 10 items
- Stored in config.ini under `[Find]` section
- Methods:
  - `config_manager.get_search_history()` → List[str]
  - `config_manager.add_search_to_history(text: str)`
  - `config_manager.save_config()`

### Command History
- Similar pattern for command history
- Maximum 100 items
- Methods:
  - `config_manager.get_command_history()` → List[str]
  - `config_manager.add_command_to_history(cmd: str)`

## 🎨 UI Development Rules

### Dialog Windows
- Use `Qt.Tool` flag for utility windows to avoid taskbar
- Keep close button and system menu: `Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint`
- Set `setModal(False)` for non-blocking dialogs

### Resizable Floating Windows
```python
# Set window flags
current_flags = self.windowFlags()
new_flags = current_flags | Qt.Tool
new_flags |= Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint
self.setWindowFlags(new_flags)

# Allow resizing
self.setModal(False)
```

### History ComboBoxes
```python
# Make editable combo with history
combo = QComboBox()
combo.setEditable(True)
combo.setMaxCount(10)  # Maximum items

# Access line edit
combo.lineEdit().setPlaceholderText(text)
combo.lineEdit().textChanged.connect(handler)
combo.lineEdit().returnPressed.connect(handler)
```

## 🔍 Feature-Specific Rules

### Find Dialog
- Input: Editable QComboBox (not QLineEdit)
- Support regex mode with QRegularExpression
- Save search history automatically on search
- Maximum 10 history items

### Find All Results
- Show in separate resizable window
- Allow double-click to jump to result
- Support copy selected/all results
- Display line numbers and context

## ⚠️ Important Reminders

1. **所有注释必须使用中文** - 单行注释、多行注释、文档字符串都要用中文
2. **禁止使用EMOJI表情** - 代码中任何地方都不得使用EMOJI（🔧📋💾等）
3. **禁止硬编码中文字符串** - 所有用户可见文本必须使用`QCoreApplication.translate()`
4. **标识符必须使用英文** - 类名、方法名、变量名都用英文，不要混用中英文
5. **日志输出也要翻译** - logger和print输出也应使用translate处理
6. **不要主动提交或编译** - 只提出建议，等待用户批准
7. **保持翻译上下文一致** - translate的context参数要与类名一致
8. **完整提取翻译** - lupdate命令必须包含所有.py和.ui文件
9. **不要手动编辑.ts文件** - 使用Python脚本或Qt Linguist工具
10. **测试多语言切换** - 确保中英文都能正常显示

## 📖 Reference Examples

### Good Code Structure
```python
class MyDialog(QDialog):
    """My Dialog - English docstring"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set translated window title
        self.setWindowTitle(QCoreApplication.translate("MyDialog", "My Dialog"))
        
        # Setup UI
        self.setup_ui()
    
    def setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)
        
        # Label with translation
        label = QLabel(QCoreApplication.translate("MyDialog", "Enter name:"))
        layout.addWidget(label)
        
        # Input with translated placeholder
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(
            QCoreApplication.translate("MyDialog", "Type your name...")
        )
        layout.addWidget(self.name_input)
        
        # Button with translation
        btn = QPushButton(QCoreApplication.translate("MyDialog", "OK"))
        btn.clicked.connect(self.on_ok_clicked)
        layout.addWidget(btn)
    
    def on_ok_clicked(self):
        """Handle OK button click"""
        name = self.name_input.text()
        if not name:
            QMessageBox.warning(
                self,
                QCoreApplication.translate("MyDialog", "Warning"),
                QCoreApplication.translate("MyDialog", "Please enter a name.")
            )
```

## 💻 Windows PowerShell 环境规则

### AI运行环境说明
AI助手运行在Windows PowerShell环境中，必须正确处理中文编码问题。

### 编码问题与解决方案

#### 问题1: Python脚本输出中文乱码
**现象**：
```
[OK] �Ѽ����ļ�: main_window.py
���� 2334 ��EMOJI����
```

**原因**：
- PowerShell默认使用GBK编码
- Python print输出UTF-8字符时会乱码
- 特殊Unicode字符（如✓、EMOJI）无法在GBK下正确显示

**解决方案**：

##### 方案1: 使用ASCII替代字符（推荐）
```python
# ❌ 错误：使用特殊Unicode字符
print(f"✓ 已加载文件: {filepath}")
print(f"⚠ 发现问题")

# ✅ 正确：使用ASCII或纯文本
print(f"[OK] 已加载文件: {filepath}")
print(f"[WARNING] 发现问题")
print(f"成功: 已加载文件: {filepath}")
```

##### 方案2: 避免输出中文到控制台
```python
# ❌ 错误：在自动化脚本中输出中文
def process_files():
    print("正在处理文件...")  # 会乱码
    print(f"处理了 {count} 个文件")  # 会乱码

# ✅ 正确：使用英文或写入文件
def process_files():
    print(f"Processing {count} files...")  # 英文不会乱码
    # 或者将详细信息写入UTF-8文件
    with open('report.txt', 'w', encoding='utf-8') as f:
        f.write(f"处理了 {count} 个文件\n")
```

##### 方案3: 设置PowerShell UTF-8编码
```powershell
# 在执行Python脚本前设置编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
python script.py

# 或者创建一个包装脚本
# run_with_utf8.ps1
param($ScriptPath)
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
python $ScriptPath
```

##### 方案4: 使用批处理文件
```batch
@echo off
chcp 65001 > nul
python script.py
```

#### 问题2: EMOJI无法在PowerShell中显示
**现象**：
```python
print("🔧 配置中...")  # 导致 UnicodeEncodeError
```

**原因**：
EMOJI是高位Unicode字符（U+1F000以上），PowerShell的GBK编码无法表示。

**解决方案**：
```python
# ✅ 绝对不要在代码中使用EMOJI
print("[CONFIG] 配置中...")
print(">> 配置中...")
```

#### 问题3: 文件读写编码问题
**现象**：
```python
# 读取文件时出现乱码或UnicodeDecodeError
with open('file.txt', 'r') as f:  # 错误：未指定编码
    content = f.read()
```

**解决方案**：
```python
# ✅ 始终显式指定UTF-8编码
with open('file.txt', 'r', encoding='utf-8') as f:
    content = f.read()

with open('file.txt', 'w', encoding='utf-8') as f:
    f.write(content)

# ✅ 处理异常情况
import codecs
try:
    with codecs.open('file.txt', 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
except UnicodeDecodeError as e:
    print(f"[ERROR] Encoding error: {e}")
```

### Python脚本编写规范

#### 1. 文件头部必须声明编码
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块说明
"""
```

#### 2. 所有print输出使用ASCII安全字符
```python
# ✅ 推荐的状态标记
print("[OK]")      # 成功
print("[ERROR]")   # 错误
print("[WARNING]") # 警告
print("[INFO]")    # 信息
print("[DEBUG]")   # 调试

# ✅ 或使用简单符号
print("+ 成功")
print("- 失败")
print("* 处理中")
print("> 提示")

# ❌ 不要使用
print("✓")  # 可能乱码
print("✗")  # 可能乱码
print("⚠")  # 可能乱码
print("🔧") # 绝对会出错
```

#### 3. 避免在异常信息中使用中文
```python
# ❌ 错误
raise ValueError("参数不能为空")  # 异常信息可能乱码

# ✅ 正确
raise ValueError("Parameter cannot be empty")

# ✅ 或者分离显示
try:
    validate_param(param)
except ValueError as e:
    print(f"[ERROR] {e}")
    with open('error_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"错误: 参数不能为空\n")
```

#### 4. 使用日志而非print
```python
import logging

# 配置日志输出到文件（UTF-8编码）
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'  # Python 3.9+
)

# 或者对于旧版本Python
import codecs
import sys

class UTF8StreamHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__(sys.stdout)
        
    def emit(self, record):
        try:
            msg = self.format(record)
            # 写入文件而非控制台
            with open('app.log', 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception:
            self.handleError(record)
```

### 自动化脚本最佳实践

#### 脚本模板
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本说明
"""

import sys
import os

def main():
    """主函数"""
    print("=" * 80)
    print("Script Name")
    print("=" * 80)
    
    try:
        # 业务逻辑
        result = process_data()
        
        # 输出结果到文件
        output_file = "result.txt"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"处理结果: {result}\n")
        
        print(f"[OK] Result saved to {output_file}")
        return 0
        
    except Exception as e:
        print(f"[ERROR] {e}")
        # 详细错误信息写入文件
        with open("error.log", 'a', encoding='utf-8') as f:
            import traceback
            f.write(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

### 检查清单

运行Python脚本前检查：

- [ ] 文件头部有 `# -*- coding: utf-8 -*-`
- [ ] 所有 `open()` 都指定了 `encoding='utf-8'`
- [ ] print输出只使用ASCII字符：`[OK]`, `[ERROR]` 等
- [ ] 没有使用EMOJI或特殊Unicode符号
- [ ] 如果需要输出中文，使用文件输出而非print
- [ ] 异常消息使用英文
- [ ] 考虑使用logging模块输出到文件

## 🚀 Git Commit Rules

### Commit Message Encoding
- **Always use UTF-8 file method** for commits with Chinese characters
- Never use `git commit -m "中文"` directly in PowerShell
- Use helper script or file method

### Commit Helper
```powershell
# Use the helper script
.\\.git-commit-helper.ps1 "提交信息"

# Or use file method
$msg | Out-File -FilePath .git-commit-msg.tmp -Encoding UTF8 -NoNewline
git commit -F .git-commit-msg.tmp
Remove-Item .git-commit-msg.tmp -Force
```

See `GIT_COMMIT_RULES.md` for details.

