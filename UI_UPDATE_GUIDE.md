# 连接界面UI更新指南

## 📋 更新内容

本次更新包含了连接界面的优化，主要改进如下：

### 🔧 主要改进

1. **串口显示优化**
   - 串口下拉框现在显示友好名称（如：`COM3 - JLink CDC UART Port`）
   - 自动截取前20个字符，避免显示内容过长
   - 智能去除重复的端口名信息

2. **新增串口转发设置**
   - 添加了串口转发配置组框
   - 支持两种转发模式：
     - `LOG Current Tab Selection` - 转发当前选中TAB的日志内容
     - `DATA (RTT Channel 1)` - 转发RTT通道1的原始数据
   - 转发内容选择下拉框

3. **界面布局优化**
   - 调整UART配置区域布局，波特率独立一行
   - 增加对话框高度以容纳新功能
   - 优化控件间距和对齐

## 📁 文件说明

### 新增文件

- `rtt2uart_updated.ui` - 更新后的UI定义文件
- `ui_rtt2uart_updated.py` - 从UI文件生成的Python代码
- `UI_UPDATE_GUIDE.md` - 本使用指南

### 修改的现有文件

- `main_window.py` - 
  - 修改了 `port_scan()` 方法以显示友好名称
  - 添加了 `get_selected_port_name()` 方法提取实际端口名
  - 更新了串口使用的地方以调用新方法

## 🛠️ 使用Qt Designer调整界面

### 步骤1：使用Qt Designer打开文件
```bash
pyside6-designer rtt2uart_updated.ui
```

### 步骤2：在Qt Designer中调整
- 调整控件位置和大小
- 修改控件属性
- 添加或删除控件
- 设置布局管理器

### 步骤3：重新生成Python代码
```bash
pyside6-uic rtt2uart_updated.ui -o ui_rtt2uart_updated.py
```

### 步骤4：在代码中应用
将 `main_window.py` 中的：
```python
from ui_rtt2uart import Ui_dialog
```
改为：
```python
from ui_rtt2uart_updated import Ui_dialog
```

## 📐 当前界面布局

```
┌─ Connection to J-Link ────────────────────┐
│ ○ USB          □ Serial NO: [________]    │
│ ○ TCP/IP       IP: [___________________]  │
│ ○ Existing Session  □ Auto Reconnect     │
└───────────────────────────────────────────┘

┌─ Specify Target Device ───────────────────┐
│ [Device Dropdown________________] [...]   │
└───────────────────────────────────────────┘

┌─ Target Interface And Speed ──────────────┐
│ [Interface Dropdown_____] [Speed Dropdown]│
└───────────────────────────────────────────┘

□ Reset target

────────────────────────────────────────────

┌─ UART Config ─────────────────────────────┐
│ Port:     [COM3 - JLink CDC UART...] [Scan]│
│ Baud rate: [115200_________________]       │
└───────────────────────────────────────────┘

┌─ Serial Forward Settings ─────────────────┐
│ ○ LOG Current Tab Selection               │
│ ○ DATA (RTT Channel 1)                    │
│ Forward Content: [Dropdown_______________] │
└───────────────────────────────────────────┘

                [Start Button]
```

## 🎯 关键改进点

1. **串口友好名称显示**：更容易识别设备类型
2. **两行式UART配置**：避免界面拥挤
3. **串口转发可视化配置**：替代了原来的代码动态创建
4. **更合理的控件尺寸**：适应更长的设备名称

## 🔄 从代码动态创建迁移到UI文件的优势

- ✅ 可视化设计和调整
- ✅ 更清晰的布局结构
- ✅ 更容易维护和修改
- ✅ 支持Qt Designer的所见即所得编辑
- ✅ 更好的国际化支持

现在您可以使用Qt Designer工具来可视化调整连接界面，无需在代码中手动计算控件位置！
