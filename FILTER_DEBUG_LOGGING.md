# 筛选值清空问题调试日志

## 问题描述
筛选值会出现意外清空的情况：
- 配置文件中已经没有筛选值
- 但UI上显示的筛选值没有被修改
- 这个问题已经修复了10多个版本仍未解决

## 调试策略

为了追踪筛选值何时被清空，我们在以下关键位置添加了详细的日志：

### 1. 配置保存 (`config_manager.py::save_config()`)

**日志标识**: 🔵🔵🔵... (蓝色)

**记录内容**:
- 调用栈（最近5层）
- 当前配置中所有非空的筛选值
- 是否跳过保存（脏数据检测）

**示例输出**:
```
🔵🔵🔵...
[CONFIG SAVE] save_config() 被调用
[CONFIG SAVE] 调用栈:
[CONFIG SAVE]   1. main_window.py:3393 in on_font_changed
[CONFIG SAVE]   2. ...
[CONFIG SAVE] 当前配置中的筛选值:
[CONFIG SAVE]   filter_17 = 'test'
[CONFIG SAVE]   filter_18 = 'debug'
[CONFIG SAVE] ✅ 配置保存成功: C:\Users\...\config.ini
🔵🔵🔵...
```

### 2. 筛选值修改 (`config_manager.py::set_filter()`)

**日志标识**: 🟢🟢🟢... (绿色)

**记录内容**:
- 调用栈（最近3层）
- 修改前的值
- 修改后的值

**示例输出**:
```
🟢🟢🟢...
[FILTER SET] set_filter(17, 'new_value')
[FILTER SET] 调用栈:
[FILTER SET]   1. main_window.py:913 in mouseDoubleClickEvent
[FILTER SET]   2. ...
[FILTER SET] 修改前: filter_17 = 'old_value'
[FILTER SET] 修改后: filter_17 = 'new_value'
🟢🟢🟢...
```

### 3. 用户双击编辑 (`main_window.py::mouseDoubleClickEvent()`)

**日志标识**: 🟡🟡🟡... (黄色)

**记录内容**:
- TAB索引
- 原文本
- 新文本
- 正则表达式状态
- save_config() 调用前后

**示例输出**:
```
🟡🟡🟡...
[FILTER EDIT] 用户双击编辑TAB 17
[FILTER EDIT] 原文本: 'old_filter'
[FILTER EDIT] 新文本: 'new_filter'
[FILTER EDIT] 正则: False
[FILTER EDIT] 准备调用 save_config()
[FILTER EDIT] save_config() 调用完成
🟡🟡🟡...
```

### 4. 中键点击清空 (`main_window.py::mousePressEvent()`)

**日志标识**: 🔴🔴🔴... (红色)

**记录内容**:
- TAB索引
- 原文本
- save_config() 调用前后

**示例输出**:
```
🔴🔴🔴...
[MIDDLE-CLICK] 用户中键点击清空TAB 17
[MIDDLE-CLICK] 原文本: 'some_filter'
[MIDDLE-CLICK] 准备保存空字符串到配置
[MIDDLE-CLICK] 准备调用 save_config()
[MIDDLE-CLICK] save_config() 调用完成
[MIDDLE-CLICK] Cleared filter TAB 17
🔴🔴🔴...
```

### 5. F4键清空 (`main_window.py::on_clear_clicked()`)

**日志标识**: 🟣🟣🟣... (紫色)

**记录内容**:
- TAB索引
- save_config() 调用前后

**示例输出**:
```
🟣🟣🟣...
[F4 CLEAR] 用户按F4清空TAB 17
[F4 CLEAR] 准备保存空字符串到配置
[F4 CLEAR] 准备调用 save_config()
[F4 CLEAR] save_config() 调用完成
[F4 CLEAR] Saved empty filter for TAB 17
🟣🟣🟣...
```

### 6. 批量保存筛选值 (`main_window.py::_save_main_window_settings()`)

**日志标识**: 直接在日志中输出

**记录内容**:
- _filters_loaded 状态
- TAB总数
- 每个TAB的筛选值（17-32）
- 跳过保存的原因（如果跳过）

**示例输出**:
```
================================================================================
[FILTER SAVE] 开始保存筛选值到配置文件
[FILTER SAVE] _filters_loaded = True
[FILTER SAVE] TAB总数 = 33
[FILTER SAVE] TAB[17] = 'test'
[FILTER SAVE] TAB[18] = '' (默认filter文本)
[FILTER SAVE] TAB[19] = 'debug'
[FILTER SAVE] 筛选值保存完成
================================================================================
```

或者（如果跳过）:
```
================================================================================
[FILTER SAVE] ⚠️ 跳过筛选值保存！
[FILTER SAVE] 原因: _filters_loaded = False (筛选值尚未加载到UI)
================================================================================
```

## 使用方法

1. 运行程序并复现筛选值清空的问题
2. 查看控制台或日志文件，搜索以下标识：
   - 🔵 (配置保存)
   - 🟢 (筛选值修改)
   - 🟡 (双击编辑)
   - 🔴 (中键清空)
   - 🟣 (F4清空)
   - `[FILTER SAVE]` (批量保存)
3. 按时间顺序追踪事件，找出筛选值被意外清空的调用路径

## 预期结果

通过这些日志，我们应该能够：
1. 确定筛选值是在哪个操作时被清空的
2. 看到完整的调用栈，找出根本原因
3. 验证 `_filters_loaded` 标志是否正常工作
4. 确认脏数据检测是否正常工作

## 修改的文件

1. `config_manager.py`:
   - `save_config()`: 添加调用栈和当前筛选值日志
   - `set_filter()`: 添加调用栈和值变化日志

2. `main_window.py`:
   - `mouseDoubleClickEvent()`: 添加用户编辑日志
   - `mousePressEvent()`: 添加中键清空日志
   - `on_clear_clicked()`: 添加F4清空日志
   - `_save_main_window_settings()`: 添加批量保存日志

## 注意事项

- 这些日志会产生大量输出，仅用于调试
- 修复问题后应该移除或注释掉这些日志代码
- 调用栈信息可以准确定位是哪个UI操作或系统事件触发了配置保存

