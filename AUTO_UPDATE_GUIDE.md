# 差异化自动更新系统使用指南

## 🎯 系统概述

本系统实现了基于 BSDiff 算法的**增量更新**功能,可以大幅减少更新下载量(通常可节省 60-90% 的流量)。

### 核心特性

- ✅ **差异化更新**: 只下载变化的部分,不是完整文件
- ✅ **自动检测**: 启动时自动检查新版本
- ✅ **智能降级**: 如果没有差异补丁,自动下载完整文件
- ✅ **安全验证**: SHA256哈希校验确保文件完整性
- ✅ **友好界面**: 图形化更新对话框,实时显示进度
- ✅ **无缝更新**: Windows下自动替换并重启程序

---

## 📦 环境准备

### 1. 安装依赖

```bash
pip install bsdiff4 requests
```

在 `requirements.txt` 中添加:
```
bsdiff4>=1.2.0
requests>=2.25.0
```

### 2. 文件结构

```
项目根目录/
├── auto_updater.py        # 更新核心模块
├── update_dialog.py       # 更新UI对话框
├── generate_patch.py      # 补丁生成工具(服务器端)
├── main_window.py         # 主程序(需要集成)
└── version.py            # 版本信息
```

---

## 🚀 客户端集成

### 步骤1: 修改 main_window.py

在 `MainWindow.__init__` 中添加更新检查:

```python
from update_dialog import check_for_updates_on_startup

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ... 现有初始化代码 ...
        
        # 在UI初始化完成后,延迟检查更新
        check_for_updates_on_startup(self)
```

### 步骤2: 配置更新服务器URL

修改 `auto_updater.py` 中的服务器地址:

```python
# 将此修改为您的HTTP服务器地址
UPDATE_SERVER = "http://your-domain.com/xexunrtt/updates"
```

### 步骤3: 同步版本号

确保 `auto_updater.py` 中的版本号与 `version.py` 一致:

```python
# auto_updater.py
from version import __version__
CURRENT_VERSION = __version__
```

---

## 🔧 服务器端部署

### 步骤1: 准备目录结构

在您的HTTP服务器上创建目录:

```
/var/www/html/xexunrtt/updates/
├── version.json                          # 版本信息(必需)
├── XexunRTT_v2.2.0.exe                  # 当前版本
├── XexunRTT_v2.3.0.exe                  # 新版本
└── patch_2.2.0_to_2.3.0.patch           # 差异补丁
```

### 步骤2: 生成补丁和版本信息

使用 `generate_patch.py` 工具:

```bash
# 基本用法
python generate_patch.py 2.3.0 XexunRTT_v2.3.0.exe \
    --old-versions XexunRTT_v2.2.0.exe \
    --output-dir ./updates \
    --release-notes "修复了XX问题,新增了XX功能"

# 支持多个旧版本
python generate_patch.py 2.3.0 XexunRTT_v2.3.0.exe \
    --old-versions XexunRTT_v2.1.0.exe XexunRTT_v2.2.0.exe \
    --output-dir ./updates \
    --release-notes "重要更新说明"
```

输出示例:
```
新版本: 2.3.0
文件: XexunRTT_v2.3.0.exe
大小: 45.2 MB
哈希: a1b2c3d4...

正在生成补丁...
------------------------------------------------------------
正在生成补丁: XexunRTT_v2.2.0.exe -> XexunRTT_v2.3.0.exe
  旧文件: 44.8 MB
  新文件: 45.2 MB
  补丁: 3.2 MB
  节省流量: 92.9%

版本信息已更新: ./updates/version.json
============================================================
完成!
请将 ./updates 目录下的所有文件上传到您的HTTP服务器
============================================================
```

### 步骤3: 上传文件

将 `updates` 目录的内容上传到服务器:

```bash
# 使用 SCP
scp -r updates/* user@server:/var/www/html/xexunrtt/updates/

# 或使用 FTP/SFTP 客户端
```

### 步骤4: 配置HTTP服务器

确保服务器允许直接访问这些文件:

**Nginx 配置示例:**
```nginx
location /xexunrtt/updates {
    alias /var/www/html/xexunrtt/updates;
    autoindex off;
    
    # 允许跨域(可选)
    add_header Access-Control-Allow-Origin *;
    add_header Access-Control-Allow-Methods 'GET, HEAD';
    
    # 设置正确的 MIME 类型
    types {
        application/json json;
        application/octet-stream exe patch;
    }
}
```

**Apache 配置示例:**
```apache
<Directory "/var/www/html/xexunrtt/updates">
    Options -Indexes +FollowSymLinks
    AllowOverride None
    Require all granted
    
    # 设置 MIME 类型
    AddType application/json .json
    AddType application/octet-stream .exe .patch
    
    # 允许跨域(可选)
    Header set Access-Control-Allow-Origin "*"
</Directory>
```

---

## 📋 version.json 格式说明

生成的 `version.json` 文件结构:

```json
{
  "version": "2.3.0",
  "hash": "a1b2c3d4e5f6...",
  "file": "XexunRTT_v2.3.0.exe",
  "size": 47456789,
  "release_notes": "修复了XX问题\n新增了XX功能\n优化了XX性能",
  "patches": {
    "2.2.0_2.3.0": {
      "file": "patch_2.2.0_to_2.3.0.patch",
      "size": 3356789,
      "from_version": "2.2.0",
      "to_version": "2.3.0"
    },
    "2.1.0_2.3.0": {
      "file": "patch_2.1.0_to_2.3.0.patch",
      "size": 8956789,
      "from_version": "2.1.0",
      "to_version": "2.3.0"
    }
  },
  "history": [
    {
      "version": "2.2.0",
      "hash": "xyz...",
      "file": "XexunRTT_v2.2.0.exe",
      "size": 47123456
    }
  ]
}
```

---

## 🔍 更新流程详解

### 客户端流程

```
1. 程序启动 (延迟3秒)
   ↓
2. 请求 version.json
   ↓
3. 比较版本号
   ↓
4a. 无更新 → 继续运行
   ↓
4b. 有更新 → 显示更新对话框
   ↓
5. 用户选择"立即更新"
   ↓
6a. 有差异补丁 → 下载补丁 (小文件)
    ├─ 下载补丁文件 (3-10 MB)
    ├─ 应用补丁到当前exe
    └─ 验证SHA256哈希
   ↓
6b. 无差异补丁 → 下载完整文件 (大文件)
    ├─ 下载新版exe (40-50 MB)
    └─ 验证SHA256哈希
   ↓
7. 创建更新脚本 (_update.bat)
   ↓
8. 退出程序
   ↓
9. 批处理脚本:
   ├─ 备份旧版 (*.exe.old)
   ├─ 替换新版
   ├─ 重启程序
   └─ 自毁脚本
```

### 服务器端流程

```
1. 编译新版本 XexunRTT_v2.3.0.exe
   ↓
2. 收集需要支持的旧版本文件
   ├─ XexunRTT_v2.2.0.exe
   ├─ XexunRTT_v2.1.0.exe
   └─ ... (按需)
   ↓
3. 运行 generate_patch.py
   ├─ 生成差异补丁
   ├─ 计算SHA256哈希
   └─ 更新 version.json
   ↓
4. 上传到HTTP服务器
   ↓
5. 客户端可以检测到更新
```

---

## 💡 高级配置

### 1. 自定义更新检查间隔

修改 `update_dialog.py`:

```python
# 修改延迟时间(毫秒)
QTimer.singleShot(3000, do_check)  # 3秒
# 改为
QTimer.singleShot(5000, do_check)  # 5秒
```

### 2. 添加手动检查更新菜单

在主窗口菜单中添加:

```python
# main_window.py
def _create_menu(self):
    # ... 现有菜单代码 ...
    
    # 添加"检查更新"菜单项
    help_menu = self.menuBar().addMenu("帮助")
    
    check_update_action = QAction("检查更新", self)
    check_update_action.triggered.connect(self._manual_check_update)
    help_menu.addAction(check_update_action)

def _manual_check_update(self):
    """手动检查更新"""
    from auto_updater import AutoUpdater
    from update_dialog import UpdateDialog
    
    updater = AutoUpdater()
    update_info = updater.check_for_updates()
    
    if update_info:
        dialog = UpdateDialog(update_info, self)
        if dialog.exec() == QDialog.Accepted:
            import sys
            sys.exit(0)
    else:
        QMessageBox.information(
            self,
            "检查更新",
            "当前已是最新版本!",
            QMessageBox.Ok
        )
```

### 3. 跳过特定版本

```python
# 在 auto_updater.py 中添加
SKIP_VERSIONS = ['2.2.1']  # 跳过有问题的版本

def check_for_updates(self):
    # ... 现有代码 ...
    
    server_version = server_info.get('version', '')
    
    # 检查是否在跳过列表中
    if server_version in SKIP_VERSIONS:
        return None
    
    # ... 继续检查 ...
```

### 4. 更新通知频率控制

```python
# 避免频繁提示,保存上次提示时间
import time
from pathlib import Path

REMIND_INTERVAL = 24 * 3600  # 24小时

def should_remind_update(version: str) -> bool:
    """检查是否应该提醒更新"""
    cache_file = Path.home() / '.xexunrtt' / 'update_remind.txt'
    cache_file.parent.mkdir(exist_ok=True)
    
    if not cache_file.exists():
        return True
    
    try:
        with open(cache_file, 'r') as f:
            data = f.read().strip().split(',')
            last_version = data[0]
            last_time = float(data[1])
        
        # 如果是新版本或超过间隔时间
        if last_version != version or (time.time() - last_time) > REMIND_INTERVAL:
            return True
        
        return False
    except:
        return True

def mark_reminded(version: str):
    """标记已提醒"""
    cache_file = Path.home() / '.xexunrtt' / 'update_remind.txt'
    with open(cache_file, 'w') as f:
        f.write(f"{version},{time.time()}")
```

---

## 🧪 测试流程

### 1. 本地测试

```bash
# 1. 准备测试文件
mkdir test_updates
cp XexunRTT_v2.2.0.exe test_updates/
cp XexunRTT_v2.3.0.exe test_updates/

# 2. 生成补丁
python generate_patch.py 2.3.0 test_updates/XexunRTT_v2.3.0.exe \
    --old-versions test_updates/XexunRTT_v2.2.0.exe \
    --output-dir test_updates/updates \
    --release-notes "测试更新"

# 3. 启动本地HTTP服务器
cd test_updates/updates
python -m http.server 8080

# 4. 修改 auto_updater.py 中的服务器地址
UPDATE_SERVER = "http://localhost:8080"

# 5. 运行程序测试
python main_window.py
```

### 2. 验证补丁正确性

```python
# test_patch.py
import bsdiff4
from pathlib import Path
import hashlib

def test_patch(old_file, patch_file, expected_hash):
    """测试补丁是否能正确应用"""
    
    # 读取文件
    with open(old_file, 'rb') as f:
        old_data = f.read()
    
    with open(patch_file, 'rb') as f:
        patch_data = f.read()
    
    # 应用补丁
    new_data = bsdiff4.patch(old_data, patch_data)
    
    # 计算哈希
    actual_hash = hashlib.sha256(new_data).hexdigest()
    
    # 验证
    if actual_hash == expected_hash:
        print("✅ 补丁验证成功!")
        return True
    else:
        print("❌ 补丁验证失败!")
        print(f"期望: {expected_hash}")
        print(f"实际: {actual_hash}")
        return False

# 使用
test_patch(
    'XexunRTT_v2.2.0.exe',
    'patch_2.2.0_to_2.3.0.patch',
    'a1b2c3...'  # 从 version.json 中获取
)
```

---

## ⚠️ 注意事项

### 1. 文件大小限制
- BSDiff 需要将整个文件加载到内存
- 对于大文件(>100MB),可能需要较多内存
- 建议在服务器生成补丁时监控内存使用

### 2. 安全性
- **必须**使用HTTPS服务器(生产环境)
- **必须**验证SHA256哈希
- **不要**跳过哈希校验步骤

### 3. 兼容性
- Windows: 需要批处理脚本辅助更新
- macOS: 可以直接替换,但需要处理代码签名
- Linux: 可以直接替换,注意权限

### 4. 备份策略
- 自动保留 `.exe.old` 备份
- 建议保留最近2-3个版本的补丁
- 定期清理旧版本文件

### 5. 带宽优化
- 差异补丁通常节省 60-90% 流量
- 对于小改动(bug fix),效果最佳
- 对于大重构,可能效果不明显

---

## 📊 性能对比

假设完整文件大小为 45 MB:

| 更新类型 | 下载大小 | 节省流量 | 更新时间(1Mbps) |
|---------|---------|---------|----------------|
| 完整更新 | 45 MB | 0% | ~6分钟 |
| 小补丁 (bug fix) | 2-5 MB | 89-96% | ~30秒 |
| 中等补丁 (新功能) | 5-10 MB | 78-89% | ~1分钟 |
| 大补丁 (重构) | 15-20 MB | 56-67% | ~2-3分钟 |

---

## 🔧 故障排除

### 问题1: "bsdiff4 not installed"
```bash
pip install bsdiff4
# 或在虚拟环境中
pip install --upgrade bsdiff4
```

### 问题2: 补丁应用失败
- 检查旧版本文件是否匹配
- 验证补丁文件是否完整下载
- 查看日志中的详细错误信息

### 问题3: 哈希验证失败
- 重新生成补丁
- 检查文件是否在传输中损坏
- 确保 version.json 中的哈希值正确

### 问题4: 更新后程序无法启动
- 检查 `.exe.old` 备份文件
- 手动恢复: `copy XexunRTT.exe.old XexunRTT.exe`
- 重新下载完整版本

---

## 📚 相关资源

- [BSDiff 算法原理](http://www.daemonology.net/bsdiff/)
- [bsdiff4 Python库](https://github.com/ilanschnell/bsdiff4)
- [软件更新最佳实践](https://docs.microsoft.com/en-us/windows/win32/msi/patching-and-upgrades)

---

## 🎉 完成

现在您的应用已经具备了自动更新功能!

**下一步**:
1. ✅ 测试本地更新流程
2. ✅ 部署到测试服务器
3. ✅ 验证生产环境
4. ✅ 发布新版本

如有问题,请查看日志文件或联系开发团队。

