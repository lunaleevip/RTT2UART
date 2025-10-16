# XexunRTT 编码规则快速参考

## 🚫 三大禁令

### 1. 禁止使用EMOJI表情
```python
# ❌ 错误
logger.info("🪟 Window initialized")
print("✅ 成功")

# ✅ 正确
logger.info("Window initialized")
print("成功")
```

### 2. 禁止硬编码中文
```python
# ❌ 错误
button = QPushButton("确定")
print("配置文件加载成功")

# ✅ 正确
button = QPushButton(QCoreApplication.translate("ClassName", "OK"))
print(QCoreApplication.translate("main", "Config file loaded successfully"))
```

### 3. 注释必须用中文
```python
# ❌ 错误
def process_data():
    """Process the data"""  # Initialize buffer
    pass

# ✅ 正确
def process_data():
    """处理数据"""  # 初始化缓冲区
    pass
```

## ✅ 正确的代码模式

### UI元素
```python
# 按钮
btn = QPushButton(QCoreApplication.translate("ClassName", "Find"))

# 标签
label = QLabel(QCoreApplication.translate("ClassName", "Search:"))

# 下拉框
combo.addItem(QCoreApplication.translate("ClassName", "Option 1"))

# 占位符
line_edit.setPlaceholderText(QCoreApplication.translate("ClassName", "Enter text..."))
```

### 对话框
```python
QMessageBox.information(
    self,
    QCoreApplication.translate("ClassName", "Info"),
    QCoreApplication.translate("ClassName", "Operation successful")
)
```

### 日志输出
```python
# 使用logger
logger.info("Window initialized with ID: %s", window_id)
logger.debug("Command history synced: %d items", count)

# 使用print（如果需要翻译）
print(QCoreApplication.translate("main", "Config loaded successfully"))
```

## 📋 修改代码流程

1. **编写代码**
   - 标识符用英文
   - UI文本用`QCoreApplication.translate()`
   - 注释用中文
   - 不用EMOJI

2. **提取翻译**
   ```powershell
   pyside6-lupdate main_window.py xexunrtt.ui rtt2uart.ui rtt2uart_updated.ui sel_device.ui -ts xexunrtt_complete.ts
   ```

3. **更新翻译**
   - 使用Python脚本或Qt Linguist
   - 不要手动编辑.ts文件

4. **编译翻译**
   ```powershell
   pyside6-lrelease xexunrtt_complete.ts
   ```

5. **测试程序**
   ```powershell
   python main_window.py
   ```

## 💻 PowerShell 环境规则

### Python脚本输出规范
```python
# ✅ 正确：使用ASCII字符
print("[OK] File loaded")
print("[ERROR] Failed to process")
print("[WARNING] Configuration issue")

# ❌ 错误：使用特殊符号或EMOJI
print("✓ 成功")      # 会乱码
print("🔧 配置中")   # 会出错
```

### 文件操作必须指定编码
```python
# ✅ 正确
with open('file.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# ❌ 错误
with open('file.txt', 'r') as f:  # 未指定编码
    content = f.read()
```

### 运行Python脚本
```powershell
# 方法1: 使用辅助脚本（推荐）
.\run-python-utf8.ps1 script.py

# 方法2: 手动设置编码
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
python script.py
```

## 🔍 代码检查清单

在提交代码前检查：

- [ ] 所有注释都是中文
- [ ] 没有EMOJI表情符号
- [ ] 没有硬编码的中文字符串
- [ ] 所有标识符是英文
- [ ] 已提取并编译翻译文件
- [ ] 测试过中英文界面

### Python脚本检查清单

- [ ] 文件头有 `# -*- coding: utf-8 -*-`
- [ ] 所有 `open()` 都指定 `encoding='utf-8'`
- [ ] print只使用ASCII：`[OK]`, `[ERROR]` 等
- [ ] 没有EMOJI或特殊Unicode符号
- [ ] 异常消息使用英文

## 🚨 常见错误

| 错误 | 说明 | 解决方法 |
|------|------|---------|
| 日志有EMOJI | `logger.info("🔧 ...")` | 删除EMOJI，用纯文本 |
| 硬编码中文 | `QPushButton("确定")` | 改用translate |
| 英文注释 | `# Initialize buffer` | 翻译为中文 |
| 漏了.ui文件 | 翻译不完整 | lupdate包含所有.ui |
| 忘记编译.qm | 翻译不生效 | 运行lrelease |

## 📖 更多详情

完整规则请参考：[AI_CODING_RULES.md](./AI_CODING_RULES.md)

