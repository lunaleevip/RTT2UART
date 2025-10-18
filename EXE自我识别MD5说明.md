# EXE 如何识别自己的 MD5/SHA256

## 🎯 原理说明

当程序编译成 EXE 后，可以在运行时计算自己的哈希值。这是通过读取自身的可执行文件实现的。

## 📝 实现细节

### 1. 获取当前 EXE 路径

```python
def _get_current_exe(self) -> Path:
    """获取当前可执行文件路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe - 使用 sys.executable
        return Path(sys.executable)
    else:
        # 开发环境 - 返回预期的exe路径
        return Path(__file__).parent / "XexunRTT.exe"
```

**关键点**：
- `sys.frozen` 是 PyInstaller 设置的标志，表示程序已被打包
- `sys.executable` 指向当前运行的 EXE 文件完整路径
- 例如：`C:\Program Files\XexunRTT\XexunRTT.exe`

### 2. 计算文件哈希

```python
def _calculate_file_hash(self, file_path: Path) -> str:
    """计算文件SHA256哈希"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        # 分块读取，避免大文件占用过多内存
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()
```

**工作流程**：
1. 以**二进制模式**打开自己的 EXE 文件
2. 每次读取 8KB 数据块
3. 逐块计算 SHA256 哈希
4. 返回 64 字符的十六进制哈希值

### 3. 启动时自动检查

在 `check_for_updates()` 方法中：

```python
# 获取服务器版本信息
server_info = requests.get(version_url).json()

# 计算当前EXE的哈希
current_hash = self._calculate_file_hash(self.current_exe)
logger.info(f"Current file hash: {current_hash[:16]}...")

# 验证完整性
integrity_check = self._verify_current_file_integrity(
    current_hash, 
    self.current_version, 
    server_info
)
```

## 🔐 完整性验证逻辑

### 验证流程

```python
def _verify_current_file_integrity(self, current_hash, current_version, server_info):
    # 1. 检查是否是最新版本
    if current_version == server_info['version']:
        if current_hash == server_info['hash']:
            return "verified"  # ✅ 完整性通过
        else:
            return "modified"  # ⚠️ 文件被修改

    # 2. 检查历史版本记录
    for hist in server_info['history']:
        if hist['version'] == current_version:
            if current_hash == hist['hash']:
                return "verified"  # ✅ 历史版本验证通过
            else:
                return "modified"  # ⚠️ 文件被修改

    # 3. 检查补丁记录中的源文件哈希
    for patch_info in server_info['patches'].values():
        if patch_info.get('from_version') == current_version:
            if current_hash == patch_info.get('from_hash'):
                return "verified"  # ✅ 补丁源验证通过
            else:
                return "modified"  # ⚠️ 文件被修改

    # 4. 无法验证（服务器没有该版本记录）
    return "unknown"  # ❓ 未知状态
```

## 📊 验证结果处理

### 结果 1: `verified` - 验证通过 ✅

```python
if integrity_check == "verified":
    logger.info("✅ Current file integrity verified")
    # 继续正常的版本检查流程
```

### 结果 2: `modified` - 文件被修改 ⚠️

```python
if integrity_check == "modified":
    logger.warning("⚠️ Current file has been modified!")
    # 强制完整更新，并显示警告
    return {
        'version': server_version,
        'hash': server_info['hash'],
        'full_url': f"{self.server_url}/{server_info['file']}",
        'update_type': 'full',
        'integrity_warning': True,  # 🚨 完整性警告标志
        'current_hash': current_hash
    }
```

**用户会看到**：
- ⚠️ 红色警告标题："文件完整性警告"
- 提示信息："检测到当前程序文件的完整性校验失败！文件可能已被修改、损坏或感染病毒。"
- 强烈建议立即更新

### 结果 3: 版本相同但哈希不同 🔧

```python
if version_matches and hash_differs:
    logger.warning("⚠️ Version matches but hash differs! File may be corrupted.")
    return {
        'version': server_version,
        'hash': server_info['hash'],
        'full_url': f"{self.server_url}/{server_info['file']}",
        'update_type': 'full',
        'integrity_warning': True,
        'is_repair': True  # 🔧 修复标志
    }
```

**用户会看到**：
- ⚠️ 橙色修复标题："文件完整性警告"
- 提示信息："文件可能已被篡改或损坏。建议更新到最新版本以确保安全。"

## 🎨 实际运行示例

### 场景 1: 正常启动（文件未修改）

```
2025-10-18 16:26:42 - [INFO] Checking for updates from: http://...
2025-10-18 16:26:42 - [INFO] Current file hash: a1b2c3d4e5f6...
2025-10-18 16:26:42 - [INFO] ✅ Current file integrity verified
2025-10-18 16:26:42 - [INFO] No update needed. Current version and hash match.
```

### 场景 2: 文件被修改

```
2025-10-18 16:26:42 - [INFO] Current file hash: 9999aaaabbbb...
2025-10-18 16:26:42 - [WARNING] ⚠️ Current file has been modified!
2025-10-18 16:26:42 - [WARNING]    Expected hash for v2.4 not found in server records
2025-10-18 16:26:42 - [WARNING]    Current hash: 9999aaaabbbb...
```

**弹出对话框**：
```
⚠️ 文件完整性警告

⚠️ 检测到当前程序文件的完整性校验失败！
文件可能已被修改、损坏或感染病毒。
强烈建议立即修复以确保程序安全运行。

版本: 2.4 → 2.5
大小: 45.2 MB

[ 立即更新 ]  [ 稍后提醒 ]
```

### 场景 3: 文件损坏（版本相同，哈希不同）

```
2025-10-18 16:26:42 - [INFO] Current file hash: ccccddddeeee...
2025-10-18 16:26:42 - [WARNING] ⚠️ Version matches but hash differs!
2025-10-18 16:26:42 - [WARNING]    Current: ccccddddeeee...
2025-10-18 16:26:42 - [WARNING]    Expected: a1b2c3d4e5f6...
```

## 🔧 技术要点

### 1. 为什么使用 SHA256 而不是 MD5？

- ✅ **SHA256 更安全**：抗碰撞能力更强
- ✅ **行业标准**：Git、Docker 等都使用 SHA256
- ✅ **性能足够**：计算速度对 40-50MB 的 EXE 文件来说完全可接受

### 2. 分块读取的优势

```python
while chunk := f.read(8192):  # 每次8KB
    sha256.update(chunk)
```

- 💾 **节省内存**：不需要一次性加载整个 EXE 到内存
- ⚡ **性能优化**：8KB 是磁盘 I/O 的最佳块大小
- 📦 **支持大文件**：即使 EXE 有几百 MB 也能处理

### 3. PyInstaller 特殊处理

```python
if getattr(sys, 'frozen', False):
    # 打包后: sys.executable = "C:\...\XexunRTT.exe"
    return Path(sys.executable)
else:
    # 开发中: 返回预期路径（用于测试）
    return Path(__file__).parent / "XexunRTT.exe"
```

## 📝 服务器端 version.json 格式

```json
{
  "version": "2.4",
  "hash": "a1b2c3d4e5f6789012345678901234567890123456789012345678901234567890",
  "file": "XexunRTT_v2.4_win.exe",
  "size": 47456789,
  "history": [
    {
      "version": "2.3",
      "hash": "earlier_version_hash...",
      "size": 46000000
    }
  ],
  "patches": {
    "2.3_2.4": {
      "file": "patch_2.3_to_2.4.bsdiff",
      "size": 2456789,
      "from_version": "2.3",
      "to_version": "2.4",
      "from_hash": "earlier_version_hash..."  // 🔑 关键：源文件哈希
    }
  }
}
```

## 🚀 使用流程

1. **程序启动** → 5秒后自动检查更新
2. **计算哈希** → 读取自身 EXE，计算 SHA256
3. **对比验证** → 与服务器记录的哈希对比
4. **显示结果** → 根据验证结果决定是否显示警告

## ✅ 总结

- 📍 **自我识别**：通过 `sys.executable` 获取自身路径
- 🔐 **哈希计算**：分块读取，使用 SHA256 算法
- 🛡️ **完整性验证**：对比服务器记录，检测篡改
- ⚠️ **安全警告**：如发现异常，强制更新并警告用户

这套机制确保了：
- ✅ 用户运行的是**未被篡改**的正版程序
- ✅ 自动检测文件**损坏**或**病毒感染**
- ✅ 提供**修复**和**更新**的安全途径

