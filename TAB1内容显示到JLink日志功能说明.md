# TAB 1内容显示到JLink日志功能说明

## 🔍 功能描述

当命令发送成功后，自动将TAB 1 (RTT Channel 1) 的输出内容展示到JLink日志框中，方便用户查看命令执行后的设备响应。

## 🎯 使用场景

- **命令调试**: 发送命令后立即查看设备响应
- **日志整合**: 将命令和响应集中显示在JLink日志中
- **快速反馈**: 无需切换TAB即可看到响应结果
- **历史记录**: 在JLink日志中保留命令执行历史

## ✨ 功能特性

### 1. **智能内容获取**
- 自动获取TAB 1 (RTT Channel 1) 的当前内容
- 智能截取最近的500个字符，避免内容过长
- 从完整行开始截取，保持内容完整性

### 2. **延迟响应机制**
- 延迟100ms获取内容，等待设备可能的响应数据
- 确保能捕获到命令执行后的输出

### 3. **内容智能处理**
- 自动清理ANSI控制字符，保持日志整洁
- 只显示最近5行内容，避免日志过长
- 过滤空行，只显示有效内容

### 4. **友好的格式化输出**
```
📤 Command sent: ver?
📥 RTT Channel 1 Response:
   [15:09:16.997] sensor_activity_detect[2244] 活动检测
   [15:09:17.005] sensor_activity_detect[2244] 活动检测  
   [15:09:17.013] RTT LEN: 4 DATA: ver?
──────────────────────────────────────────────────
```

## 🛠️ 技术实现

### 核心方法

#### 1. `get_tab1_content()`
```python
def get_tab1_content(self):
    """获取TAB 1 (RTT Channel 1) 的当前内容"""
    try:
        # TAB 1对应索引1（索引0是ALL页面）
        tab_index = 1
        
        # 获取TAB 1的widget
        tab1_widget = self.ui.tem_switch.widget(tab_index)
        if not tab1_widget:
            return ""
        
        # 查找文本框
        text_edit = tab1_widget.findChild(QPlainTextEdit)
        if not text_edit:
            text_edit = tab1_widget.findChild(QTextEdit)
        
        if text_edit:
            # 获取文本内容
            content = text_edit.toPlainText()
            
            # 返回最近的内容（最后500个字符，避免过长）
            max_chars = 500
            if len(content) > max_chars:
                # 获取最后的内容，并尝试从完整行开始
                recent_content = content[-max_chars:]
                first_newline = recent_content.find('\n')
                if first_newline != -1:
                    recent_content = recent_content[first_newline + 1:]
                return recent_content
            else:
                return content
        
        return ""
        
    except Exception as e:
        logger.error(f"❌ 获取TAB 1内容失败: {e}")
        return ""
```

#### 2. `_display_tab1_content_to_jlink_log(command)`
```python
def _display_tab1_content_to_jlink_log(self, command):
    """将TAB 1的内容显示到JLink日志框中"""
    try:
        # 延迟一小段时间，等待可能的响应数据
        QTimer.singleShot(100, lambda: self._delayed_display_tab1_content(command))
        
    except Exception as e:
        logger.error(f"❌ 显示TAB 1内容到JLink日志失败: {e}")
```

#### 3. `_delayed_display_tab1_content(command)`
```python
def _delayed_display_tab1_content(self, command):
    """延迟显示TAB 1内容（等待响应数据）"""
    try:
        # 获取TAB 1的当前内容
        tab1_content = self.get_tab1_content()
        
        if tab1_content.strip():
            # 分割内容为行
            lines = tab1_content.strip().split('\n')
            
            # 只显示最近的几行（避免过多内容）
            max_lines = 5
            recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines
            
            # 添加到JLink日志
            self.append_jlink_log(f"📤 Command sent: {command}")
            self.append_jlink_log("📥 RTT Channel 1 Response:")
            
            for line in recent_lines:
                line = line.strip()
                if line:  # 只显示非空行
                    # 清理ANSI控制字符
                    import re
                    clean_line = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)
                    self.append_jlink_log(f"   {clean_line}")
            
            self.append_jlink_log("─" * 50)  # 分隔线
        else:
            # 如果没有内容，显示提示信息
            self.append_jlink_log(f"📤 Command sent: {command}")
            self.append_jlink_log("📥 RTT Channel 1: No response data")
            self.append_jlink_log("─" * 50)  # 分隔线
            
    except Exception as e:
        logger.error(f"❌ 延迟显示TAB 1内容失败: {e}")
```

### 集成到命令发送流程

在`on_pushButton_clicked()`方法中，当命令发送成功后调用：

```python
# 检查发送是否成功
if(bytes_written == len(out_bytes)):
    # ... 原有的成功处理逻辑 ...
    
    # 📋 新功能：命令发送成功后，将TAB 1的输出内容展示到JLink日志框
    self._display_tab1_content_to_jlink_log(current_text)
    
    # ... 其他处理逻辑 ...
```

## 🎮 用户体验

### 使用流程
1. **发送命令**: 在命令输入框中输入命令并点击"Send"按钮
2. **自动显示**: 命令发送成功后，自动在JLink日志中显示：
   - 📤 发送的命令
   - 📥 TAB 1的响应内容
   - ─ 分隔线区分不同命令
3. **实时更新**: JLink日志自动滚动到底部显示最新内容

### 界面效果
- **命令标识**: 使用📤图标标识发送的命令
- **响应标识**: 使用📥图标标识设备响应
- **内容缩进**: 响应内容使用缩进显示，便于区分
- **分隔线**: 使用分隔线区分不同命令的执行记录
- **时间戳**: 每条日志都有时间戳，便于追踪

## 📊 功能优势

### 1. **提升调试效率**
- 无需在TAB之间切换查看响应
- 命令和响应集中显示，便于分析
- 保留历史记录，便于对比

### 2. **智能内容管理**
- 自动截取合适长度的内容
- 过滤无效信息，只显示关键响应
- 清理格式字符，保持日志整洁

### 3. **用户友好**
- 图标化显示，直观易懂
- 格式化输出，结构清晰
- 自动滚动，始终显示最新内容

## 🔧 配置选项

### 可调整参数
- **内容截取长度**: 默认500字符，可根据需要调整
- **显示行数**: 默认最多5行，避免日志过长
- **延迟时间**: 默认100ms，可根据设备响应速度调整

### 自定义修改
如需调整参数，可修改以下代码：

```python
# 在get_tab1_content()方法中
max_chars = 500  # 调整最大字符数

# 在_delayed_display_tab1_content()方法中  
max_lines = 5    # 调整最大显示行数

# 在_display_tab1_content_to_jlink_log()方法中
QTimer.singleShot(100, ...)  # 调整延迟时间(ms)
```

## 🧪 测试验证

### 功能测试覆盖
- ✅ TAB 1内容获取功能
- ✅ JLink日志显示功能  
- ✅ 命令发送集成功能
- ✅ 内容格式化处理
- ✅ 延迟响应机制
- ✅ 异常处理机制

### 测试场景
1. **有响应数据**: 正常显示命令和响应
2. **无响应数据**: 显示"No response data"提示
3. **长内容**: 智能截取最近的内容
4. **多行内容**: 只显示最近几行
5. **ANSI字符**: 自动清理控制字符

## 🚀 未来扩展

### 可能的增强功能
1. **多TAB支持**: 支持显示其他TAB的内容
2. **过滤配置**: 允许用户配置显示哪些内容
3. **导出功能**: 支持导出命令执行历史
4. **高亮显示**: 对关键信息进行高亮标识
5. **搜索功能**: 在JLink日志中搜索特定内容

### 性能优化
- 异步内容获取，避免UI阻塞
- 智能缓存机制，减少重复处理
- 内存管理优化，控制日志大小

## 📋 使用建议

### 最佳实践
1. **适度使用**: 对于频繁发送的命令，注意日志大小
2. **及时清理**: 定期清理JLink日志，避免内容过多
3. **合理配置**: 根据设备特性调整延迟时间
4. **关注响应**: 观察响应内容，及时发现异常

### 注意事项
- 功能依赖于TAB 1有有效内容
- 延迟机制可能不适用于所有设备
- 长时间运行需要注意内存使用
- 建议结合其他调试工具使用

---

*此功能大大提升了命令调试的便利性，让用户能够更高效地进行设备交互和问题排查*
