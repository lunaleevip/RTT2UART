# 🎉 XexunRTT v2.1.1 发布说明

**发布日期**: 2025年9月23日  
**版本类型**: 重大BUG修复版本  
**构建状态**: ✅ 成功  

## 🚨 重大修复

### 1. **Worker缓存污染修复**（关键修复）
- **问题描述**: 重新连接时新文件夹包含大量历史日志数据
- **根本原因**: Worker对象缓存未清理，`log_buffers`积累历史数据
- **修复方案**: 
  - 在`ConnectionDialog.start`中添加`_clear_all_worker_caches()`调用
  - 彻底清空所有类型缓存：`log_buffers`, `buffers`, `colored_buffers`
  - 同步清空UI显示内容
- **修复效果**: 新文件夹只包含当前连接的数据

### 2. **滚动条锁定状态保存修复**
- **问题描述**: 取消滚动条锁定后重新连接时自动重新锁定
- **根本原因**: `on_lock_h_changed`和`on_lock_v_changed`只保存配置文件，未更新`settings`字典
- **修复方案**:
  - 修复两个方法同时更新`settings`字典和配置文件
  - 确保状态保存的一致性
- **修复效果**: 滚动条锁定状态正确保持

## 🎯 技术细节

### 缓存清理机制
```python
def _clear_all_worker_caches(self):
    """🚨 彻底清空Worker的所有缓存"""
    # 清空数据缓冲区
    worker.buffers[i].clear()
    worker.colored_buffers[i].clear()
    # 清空日志文件缓冲区（关键）
    worker.log_buffers.clear()
    # 清空UI显示
    self._clear_main_window_ui()
```

### 状态保存修复
```python
def on_lock_h_changed(self):
    """水平滚动条锁定状态改变时保存配置"""
    # 同时更新settings字典和配置文件
    self.connection_dialog.settings['lock_h'] = self.ui.LockH_checkBox.isChecked()
    self.connection_dialog.config.set_lock_horizontal(self.ui.LockH_checkBox.isChecked())
    self.connection_dialog.config.save_config()
```

## 📊 构建信息

- **EXE文件大小**: 2.4 MB
- **总大小**: 121.4 MB
- **构建工具**: PyInstaller 6.15.0
- **Python版本**: 3.13.6
- **构建模式**: 增量更新模式

## 🎯 修复效果对比

| 功能 | 修复前 | 修复后 |
|------|--------|--------|
| 新文件夹数据 | 包含历史数据 ❌ | 只有当前数据 ✅ |
| 滚动条状态 | 自动重新锁定 ❌ | 正确保持状态 ✅ |
| 缓存管理 | 累积污染 ❌ | 彻底清理 ✅ |
| 配置保存 | 部分失效 ❌ | 双重保存 ✅ |

## ⚠️ 兼容性说明

- ✅ 完全向后兼容现有配置文件
- ✅ 不影响其他功能的正常使用
- ✅ 保持所有现有功能特性
- ✅ 支持增量更新（只需替换EXE文件）

## 🚀 升级说明

### 首次安装
1. 下载 `XexunRTT_Optimized` 完整包
2. 解压到目标目录
3. 运行 `XexunRTT.exe`

### 增量升级
1. 只需替换 `XexunRTT.exe` 文件（2.4MB）
2. 保留现有配置文件和 `_internal` 目录
3. 升级效率提升 98%

## 📝 验证方法

### 缓存清理验证
1. 连接设备，等待数据写入
2. 停止连接，重新连接（创建新文件夹）
3. 检查新文件夹只包含新数据

### 滚动条状态验证
1. 锁定滚动条，然后取消锁定
2. 断开连接，重新连接
3. 验证滚动条保持未锁定状态

## 📞 支持信息

- **项目地址**: https://github.com/your-repo/XexunRTT
- **问题报告**: 通过 GitHub Issues
- **技术支持**: 详见项目文档

---

**重要提醒**: 本版本修复了影响数据完整性的重大BUG，强烈建议所有用户升级！
