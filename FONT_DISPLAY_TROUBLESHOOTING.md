# 字体显示问题排查指南

## 问题现象
在某些电脑上，即使选择相同的字体（如宋体），也可能出现以下问题：
1. 字体显示不对齐
2. 切换字体或大小后不立即生效，需要重启程序

## 可能的原因

### 1. **系统字体渲染引擎差异**
- Windows不同版本的字体渲染引擎（GDI、DirectWrite）行为不同
- 显示器DPI缩放设置不同
- 系统字体平滑设置（ClearType）配置不同

### 2. **Qt字体缓存**
- Qt会缓存字体信息，某些情况下不会立即更新
- 不同版本的PySide6/Qt行为可能不同

### 3. **字体文件版本差异**
- 不同电脑上安装的"宋体"可能是不同版本
- 字体文件损坏或不完整

## 已实施的改进

### v2.2版本改进
```python
# 使用更严格的等宽字体设置
font.setStyleHint(QFont.TypeWriter)  # 使用TypeWriter而不是Monospace
font.setStyleStrategy(QFont.PreferDefault | QFont.ForceIntegerMetrics)  # 强制整数度量
font.setKerning(False)  # 禁用字距调整

# 强制刷新机制
QApplication.processEvents()  # 立即处理事件
QTimer.singleShot(100, self._delayed_font_refresh)  # 延迟二次刷新
```

## 用户解决方案

### 方案1：调整系统设置
1. **检查DPI缩放**
   - 右键桌面 → 显示设置 → 缩放与布局
   - 建议使用100%或125%
   - 修改后重启程序

2. **检查ClearType设置**
   - 搜索"ClearType" → 调整ClearType文本
   - 按向导完成设置
   - 重启程序

3. **检查字体渲染**
   - 控制面板 → 外观和个性化 → 显示 → 调整ClearType文本

### 方案2：更换字体
推荐的等宽字体（按优先级）：
1. **Consolas** - Windows内置，兼容性最好
2. **Courier New** - 经典等宽字体
3. **Microsoft YaHei Mono** - 微软雅黑等宽版
4. **更纱黑体** - 开源等宽字体，支持中文

### 方案3：重新安装字体
1. 控制面板 → 字体
2. 找到"宋体（SimSun）"
3. 右键 → 删除（需要管理员权限）
4. 重新安装宋体字体文件

### 方案4：清除Qt缓存
```batch
# 删除Qt字体缓存
del /F /Q %TEMP%\QtFontCache*
del /F /Q %LOCALAPPDATA%\fontconfig\*
```

## 程序内解决方法

### 立即生效的方法
如果切换字体后未立即生效，请：
1. 点击任意TAB标签（强制刷新当前TAB）
2. 或等待100ms（程序会自动延迟刷新）
3. 或重启程序（最保险）

### 测试字体对齐
使用以下测试文本判断字体是否对齐：
```
0123456789ABCDEF
abcdefghijklmnop
一二三四五六七八
++++++++========
||||||||--------
```
- 竖线应该完全对齐
- 中文字符应该占2个英文字符宽度

## 技术细节

### 字体度量差异
某些系统上，同样的字体因为度量方式不同导致不对齐：
- **整数度量 vs 浮点度量**：强制整数度量可以避免次像素问题
- **字距调整（Kerning）**：等宽字体必须禁用
- **字体提示（Hinting）**：TypeWriter强于Monospace

### Qt字体匹配机制
```python
# Qt字体匹配顺序
1. exactMatch() - 精确匹配字体名称
2. StyleHint - 按类型匹配替代字体
3. StyleStrategy - 字体选择策略
```

## 日志分析

查看日志中的字体信息：
```
[FONT] Loaded 93 fonts (19 monospace)
[FONT] Loaded saved font: SimSun
[FONT] Font changed to: Consolas - applying to all TABs
[FONT] Updated font for 32/32 TABs to: Consolas 10pt
```

如果字体数量异常少，说明系统字体库可能有问题。

## 联系支持

如果以上方法都无法解决，请提供以下信息：
1. Windows版本（Win 10/11，内部版本号）
2. DPI缩放设置
3. 显示器分辨率
4. 程序日志文件中的字体相关信息
5. 截图显示字体不对齐的情况

## 开发注意事项

如果需要进一步改进字体渲染，可以考虑：
1. 使用QFontMetrics测量并验证字符宽度
2. 实现自定义文本渲染
3. 使用固定像素宽度的字体
4. 添加字体渲染质量选项（性能vs质量）

