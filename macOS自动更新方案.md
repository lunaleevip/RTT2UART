# macOS 自动更新方案详解

## 🍎 macOS 应用结构

### `.app` 是什么？

```bash
XexunRTT.app/              # 看起来像文件，实际是文件夹
├── Contents/
│   ├── MacOS/
│   │   └── XexunRTT       # 👈 真正的可执行文件（二进制）
│   ├── Resources/
│   │   ├── icon.icns
│   │   └── ...
│   ├── Info.plist         # 应用元数据
│   └── Frameworks/        # Python 和依赖库
```

### 发布格式选择

| 格式 | 用途 | 说明 |
|------|------|------|
| **`.app`** | 内部使用 | 应用包本身（文件夹） |
| **`.zip`** | 自动更新 | 压缩的 .app，用于程序自动下载 ✅ |
| **`.dmg`** | 首次安装 | 磁盘镜像，用于用户手动安装 ✅ |

## 🎯 推荐方案：混合方式

### 方案概述

```
首次安装: 用户下载 .dmg
    ↓
手动拖拽安装到 /Applications
    ↓
后续更新: 程序自动下载 .zip
    ↓
自动解压替换 .app 包
```

### 详细流程

#### 1. **首次发布** - 提供 DMG

```bash
# 用户下载
XexunRTT_v2.4_macOS.dmg  (50 MB)

# DMG 内容
├── XexunRTT.app         # 拖我到 Applications
└── Applications 快捷方式
```

**优点**：
- ✅ 符合 macOS 用户习惯
- ✅ 看起来专业
- ✅ 可以包含安装说明

#### 2. **自动更新** - 使用 ZIP

```bash
# 服务器上的文件
XexunRTT_v2.5_macOS.zip  (45 MB，压缩后)

# 解压后
XexunRTT.app/            # 完整的应用包
```

**优点**：
- ✅ 易于下载和解压
- ✅ Python 内置 `zipfile` 模块
- ✅ 可以用 bsdiff 生成补丁

## 🔧 实现细节

### 1. **获取可执行文件路径**

```python
def _get_current_exe(self) -> Path:
    """获取当前可执行文件路径"""
    if getattr(sys, 'frozen', False):
        if sys.platform == "darwin":
            # macOS: /Applications/XexunRTT.app/Contents/MacOS/XexunRTT
            return Path(sys.executable)
        else:
            # Windows: C:\...\XexunRTT.exe
            return Path(sys.executable)
    else:
        # 开发环境
        if sys.platform == "darwin":
            return Path(__file__).parent / "XexunRTT.app"
        else:
            return Path(__file__).parent / "XexunRTT.exe"
```

### 2. **获取 .app 包路径**

```python
def _get_app_bundle_path(self) -> Path:
    """
    获取 .app 包的根路径
    
    例如:
    可执行文件: /Applications/XexunRTT.app/Contents/MacOS/XexunRTT
    .app 包:    /Applications/XexunRTT.app
    """
    if sys.platform == "darwin":
        # 从 .../Contents/MacOS/XexunRTT 向上3级
        # → .../Contents/MacOS → .../Contents → .../XexunRTT.app
        exe_path = Path(sys.executable)
        return exe_path.parent.parent.parent
    else:
        return self.current_exe
```

### 3. **计算 .app 包的哈希**

有两种方式：

#### 方式 A：只计算可执行文件哈希（推荐）✅

```python
def _calculate_file_hash(self, file_path: Path) -> str:
    """计算文件SHA256哈希"""
    if sys.platform == "darwin" and file_path.suffix == ".app":
        # macOS: 只计算 Contents/MacOS/XexunRTT 的哈希
        exe_path = file_path / "Contents" / "MacOS" / "XexunRTT"
        if not exe_path.exists():
            raise FileNotFoundError(f"Executable not found: {exe_path}")
        file_path = exe_path
    
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()
```

**优点**：
- ✅ 简单高效
- ✅ 只验证核心可执行文件
- ✅ 与 Windows EXE 一致

#### 方式 B：计算整个 .app 包的哈希

```python
def _calculate_app_bundle_hash(self, app_path: Path) -> str:
    """计算整个 .app 包的哈希（所有文件）"""
    import hashlib
    sha256 = hashlib.sha256()
    
    # 递归遍历所有文件
    for file_path in sorted(app_path.rglob('*')):
        if file_path.is_file():
            # 添加相对路径到哈希（保证顺序一致）
            rel_path = file_path.relative_to(app_path)
            sha256.update(str(rel_path).encode())
            
            # 添加文件内容
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
    
    return sha256.hexdigest()
```

**优缺点**：
- ✅ 更全面的完整性验证
- ❌ 计算较慢
- ❌ Resources 文件变化也会改变哈希

### 4. **macOS 更新流程**

```python
def _apply_full_update_macos(self, update_info: Dict, 
                             progress_callback=None) -> bool:
    """
    macOS 完整更新流程
    
    1. 下载 .zip 文件
    2. 解压到临时目录
    3. 验证哈希
    4. 替换当前 .app 包
    5. 重启应用
    """
    temp_dir = None
    try:
        # 1. 下载 ZIP 文件
        if progress_callback:
            progress_callback(0, 100, "正在下载更新...")
        
        temp_dir = Path(tempfile.mkdtemp())
        zip_file = temp_dir / "update.zip"
        
        self._download_file(update_info['full_url'], zip_file,
                          update_info['size'], progress_callback)
        
        # 2. 解压
        if progress_callback:
            progress_callback(0, 100, "正在解压...")
        
        extract_dir = temp_dir / "extracted"
        extract_dir.mkdir()
        
        import zipfile
        with zipfile.ZipFile(zip_file, 'r') as zf:
            zf.extractall(extract_dir)
        
        # 3. 找到 .app 包
        app_bundles = list(extract_dir.glob("*.app"))
        if not app_bundles:
            raise FileNotFoundError("No .app bundle found in ZIP")
        
        new_app = app_bundles[0]
        
        # 4. 验证哈希（只验证可执行文件）
        if progress_callback:
            progress_callback(0, 100, "正在验证完整性...")
        
        new_hash = self._calculate_file_hash(new_app)
        if new_hash != update_info['hash']:
            raise ValueError("Hash verification failed")
        
        # 5. 替换 .app 包
        if progress_callback:
            progress_callback(0, 100, "正在安装更新...")
        
        current_app = self._get_app_bundle_path()
        backup_app = current_app.with_suffix('.app.old')
        
        # 备份旧版本
        if backup_app.exists():
            shutil.rmtree(backup_app)
        shutil.move(str(current_app), str(backup_app))
        
        # 复制新版本
        shutil.copytree(new_app, current_app, symlinks=True)
        
        # 设置可执行权限
        exe_path = current_app / "Contents" / "MacOS" / "XexunRTT"
        os.chmod(exe_path, 0o755)
        
        logger.info("✅ Update installed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply update: {e}")
        
        # 如果失败，尝试恢复备份
        if backup_app and backup_app.exists():
            try:
                if current_app.exists():
                    shutil.rmtree(current_app)
                shutil.move(str(backup_app), str(current_app))
                logger.info("Restored from backup")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")
        
        return False
        
    finally:
        # 清理临时文件
        if temp_dir and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir: {e}")
```

### 5. **补丁更新（高级）**

macOS 也可以使用补丁：

```python
def _apply_patch_update_macos(self, update_info: Dict,
                              progress_callback=None) -> bool:
    """
    macOS 补丁更新流程
    
    1. 下载补丁文件
    2. 对可执行文件应用补丁
    3. 验证哈希
    4. 替换可执行文件
    """
    try:
        import bsdiff4
        
        # 1. 下载补丁
        temp_dir = Path(tempfile.mkdtemp())
        patch_file = temp_dir / "update.patch"
        
        self._download_file(update_info['patch_url'], patch_file,
                          update_info['patch_size'], progress_callback)
        
        # 2. 获取当前可执行文件
        current_exe = self.current_exe  # .../Contents/MacOS/XexunRTT
        
        # 3. 应用补丁
        with open(current_exe, 'rb') as f:
            old_data = f.read()
        
        with open(patch_file, 'rb') as f:
            patch_data = f.read()
        
        new_data = bsdiff4.patch(old_data, patch_data)
        
        # 4. 验证哈希
        import hashlib
        new_hash = hashlib.sha256(new_data).hexdigest()
        if new_hash != update_info['hash']:
            raise ValueError("Hash verification failed after patching")
        
        # 5. 替换可执行文件
        backup_exe = current_exe.with_suffix('.old')
        if backup_exe.exists():
            backup_exe.unlink()
        
        shutil.copy2(current_exe, backup_exe)
        
        with open(current_exe, 'wb') as f:
            f.write(new_data)
        
        os.chmod(current_exe, 0o755)
        
        return True
        
    except Exception as e:
        logger.error(f"Patch update failed: {e}")
        return False
```

## 📦 服务器文件结构

```
/uploads/xexunrtt/updates/
├── win/
│   ├── version.json
│   ├── XexunRTT_v2.4_win.exe
│   ├── XexunRTT_v2.5_win.exe
│   └── patch_2.4_to_2.5.bsdiff
│
└── macos/
    ├── version.json
    ├── XexunRTT_v2.4_macOS.zip     # 👈 压缩的 .app 包
    ├── XexunRTT_v2.5_macOS.zip
    ├── patch_2.4_to_2.5.bsdiff      # 👈 只针对可执行文件
    │
    └── dmg/  (可选，用于首次下载)
        ├── XexunRTT_v2.4_macOS.dmg
        └── XexunRTT_v2.5_macOS.dmg
```

### version.json 示例（macOS）

```json
{
  "version": "2.5",
  "platform": "macos",
  "hash": "a1b2c3d4...",  // 可执行文件的哈希
  "file": "XexunRTT_v2.5_macOS.zip",
  "size": 47234567,
  "release_notes": "### 新功能\n- 功能1\n- 功能2",
  "patches": {
    "2.4_2.5": {
      "file": "patch_2.4_to_2.5.bsdiff",
      "size": 1234567,
      "from_version": "2.4",
      "to_version": "2.5",
      "from_hash": "earlier..."
    }
  },
  "history": [
    {
      "version": "2.4",
      "hash": "earlier...",
      "size": 46000000
    }
  ]
}
```

## 🛠️ 创建发布文件

### 1. 编译并打包 .app

```bash
# 使用 PyInstaller
pyinstaller XexunRTT_macOS.spec

# 结果: dist/XexunRTT.app
```

### 2. 创建 ZIP（用于自动更新）

```bash
cd dist
zip -r XexunRTT_v2.5_macOS.zip XexunRTT.app
```

### 3. 创建 DMG（用于首次安装，可选）

```bash
# 方法1: 使用 hdiutil
hdiutil create -volname "XexunRTT v2.5" \
               -srcfolder dist/XexunRTT.app \
               -ov -format UDZO \
               XexunRTT_v2.5_macOS.dmg

# 方法2: 使用 create-dmg 工具
brew install create-dmg
create-dmg \
  --volname "XexunRTT v2.5" \
  --window-size 600 400 \
  --icon XexunRTT.app 150 150 \
  --app-drop-link 450 150 \
  XexunRTT_v2.5_macOS.dmg \
  dist/
```

### 4. 生成补丁

```bash
# 提取可执行文件
unzip -q XexunRTT_v2.4_macOS.zip
unzip -q XexunRTT_v2.5_macOS.zip

# 生成补丁
python generate_patch.py 2.5 \
  --old-versions XexunRTT_v2.4.app/Contents/MacOS/XexunRTT \
  --new-file XexunRTT_v2.5.app/Contents/MacOS/XexunRTT \
  --output-dir patches
```

## ✅ 最佳实践

### 推荐配置

1. **首次发布**：
   - 提供 `.dmg` 在官网下载
   - 用户习惯，看起来专业

2. **自动更新**：
   - 使用 `.zip` 格式
   - 程序自动下载、解压、替换

3. **补丁更新**：
   - 只针对 `Contents/MacOS/XexunRTT` 生成补丁
   - 节省流量，速度更快

4. **哈希验证**：
   - 只验证可执行文件哈希
   - 与 Windows 保持一致

### 优点总结

- ✅ **兼容性好**：符合 macOS 应用分发规范
- ✅ **更新快速**：ZIP 格式易于处理
- ✅ **节省流量**：支持补丁更新
- ✅ **安全可靠**：SHA256 哈希验证
- ✅ **用户友好**：DMG 首次安装，自动更新后续版本

## 🎯 总结

| 项目 | Windows | macOS |
|------|---------|-------|
| **可执行文件** | `XexunRTT.exe` | `XexunRTT.app/Contents/MacOS/XexunRTT` |
| **发布格式** | `.exe` | `.zip` (自动更新)<br>`.dmg` (首次安装) |
| **哈希计算** | 整个 EXE 文件 | 只计算可执行文件 |
| **更新方式** | 批处理脚本替换 | 直接替换 .app 包 |
| **补丁格式** | `.bsdiff` | `.bsdiff` (针对可执行文件) |

这种方案既保持了 macOS 的应用分发习惯，又实现了高效的自动更新！

