# bsdiff4 库集成说明

## 🎯 核心问题

### Q1: bsdiff4 库是否需要集成在程序中？
**答案：是的，必须集成！** ✅

### Q2: 增量更新是否需要此库？
**答案：是的，必须需要！** ✅

---

## 📦 bsdiff4 的作用

### 什么是 bsdiff4？

`bsdiff4` 是一个二进制差异工具，用于：
- **生成补丁**（服务器端）：对比两个二进制文件，生成差异补丁
- **应用补丁**（客户端）：将补丁应用到旧文件，得到新文件

### 在更新系统中的角色

```
服务器端：
  旧版本.exe + 新版本.exe → bsdiff4 → patch.bsdiff
  
客户端：
  当前.exe + patch.bsdiff → bsdiff4 → 新版本.exe
```

---

## 🔍 当前代码中的使用

### 1. 延迟导入（Lazy Import）

```python
def _apply_patch_update(self, update_info: Dict, 
                       progress_callback=None) -> bool:
    """应用差异补丁更新"""
    try:
        import bsdiff4  # 👈 只在需要时才导入
    except ImportError:
        logger.error("bsdiff4 not installed. Falling back to full update.")
        update_info['update_type'] = 'full'
        return self._apply_full_update(update_info, progress_callback)
    
    # ... 使用 bsdiff4.patch() 应用补丁
```

**特点**：
- ✅ **优雅降级**：如果没有 bsdiff4，自动回退到完整更新
- ✅ **延迟导入**：只在需要增量更新时才导入
- ✅ **不影响基本功能**：完整更新不需要 bsdiff4

### 2. 实际使用（应用补丁）

```python
# 读取旧文件
with open(self.current_exe, 'rb') as f:
    old_data = f.read()

# 读取补丁
with open(patch_file, 'rb') as f:
    patch_data = f.read()

# 应用补丁 - 这里必须用 bsdiff4！
new_data = bsdiff4.patch(old_data, patch_data)  # 👈 核心操作

# 写入新文件
with open(new_exe, 'wb') as f:
    f.write(new_data)
```

---

## 📋 PyInstaller 打包配置

### 方案 1: 自动包含（推荐）✅

PyInstaller 会自动检测并包含 `bsdiff4`：

```python
# XexunRTT_onefile_v2_2.spec
a = Analysis(
    ['main_window.py'],
    # ... 其他配置
    hiddenimports=[
        'bsdiff4',  # 👈 显式声明（可选，通常自动检测）
    ],
)
```

**验证是否包含**：
```bash
# 编译后检查
pyinstaller XexunRTT_onefile_v2_2.spec

# 在打包的 EXE 中测试
dist/XexunRTT.exe
# 程序中运行: import bsdiff4 应该不报错
```

### 方案 2: 显式添加（如果自动检测失败）

```python
# XexunRTT_onefile_v2_2.spec
a = Analysis(
    ['main_window.py'],
    hiddenimports=[
        'bsdiff4',
        'bsdiff4._bsdiff4',  # C扩展模块
    ],
)

# 或者使用 collect_submodules
from PyInstaller.utils.hooks import collect_submodules
hiddenimports = collect_submodules('bsdiff4')
```

---

## 🧪 如何验证 bsdiff4 是否已打包

### 方法 1: 运行时测试

```python
# 在打包后的程序中执行
try:
    import bsdiff4
    print("✅ bsdiff4 is available")
    print(f"   Version: {bsdiff4.__version__ if hasattr(bsdiff4, '__version__') else 'unknown'}")
except ImportError as e:
    print(f"❌ bsdiff4 not found: {e}")
```

### 方法 2: 日志查看

启动程序后查看日志：
```
# 如果有增量更新，会看到：
[INFO] Found patch from 2.4 to 2.5
[INFO] Patch size: 2456789 bytes

# 如果没有 bsdiff4：
[ERROR] bsdiff4 not installed. Falling back to full update.
```

### 方法 3: 手动检查（Windows）

```bash
# 解压 EXE（如果是单文件模式）
# EXE 运行时会解压到临时目录

# 查找 bsdiff4
# 临时目录: C:\Users\<User>\AppData\Local\Temp\_MEIxxxxxx\
# 应该能找到: _bsdiff4.pyd 或 bsdiff4.dll
```

---

## 📊 不同模式对比

### 模式 1: 完整更新（不需要 bsdiff4）

```
用户从 v2.4 → v2.5
    ↓
下载完整文件 (45 MB)
    ↓
替换旧文件
    ↓
完成
```

**依赖**：
- ✅ `requests` - 下载文件
- ✅ `hashlib` - 验证哈希（Python 内置）
- ❌ 不需要 `bsdiff4`

### 模式 2: 增量更新（必须有 bsdiff4）

```
用户从 v2.4 → v2.5
    ↓
下载补丁 (3 MB)
    ↓
bsdiff4.patch(旧文件, 补丁) → 新文件  👈 必须用 bsdiff4
    ↓
替换旧文件
    ↓
完成
```

**依赖**：
- ✅ `requests` - 下载补丁
- ✅ `hashlib` - 验证哈希
- ✅ `bsdiff4` - **必须！** 用于应用补丁

---

## 🔧 安装和集成检查清单

### 开发环境

```bash
# 1. 安装 bsdiff4
pip install bsdiff4

# 2. 验证安装
python -c "import bsdiff4; print('OK')"

# 3. 更新 requirements.txt
echo "bsdiff4>=1.2.0" >> requirements.txt
```

### 打包环境

```bash
# 1. 确保虚拟环境中有 bsdiff4
pip list | grep bsdiff4
# 应该看到: bsdiff4  1.2.x

# 2. 编译
pyinstaller XexunRTT_onefile_v2_2.spec

# 3. 测试增量更新功能
dist/XexunRTT.exe
# 尝试增量更新，查看日志
```

### 部署检查

```bash
# 1. 生成补丁（服务器端也需要 bsdiff4）
pip install bsdiff4
python generate_patch.py ...

# 2. 客户端测试
# 确保打包后的 EXE 能成功应用补丁
```

---

## ⚠️ 常见问题

### 问题 1: "bsdiff4 not installed"

**原因**：打包时未包含 bsdiff4

**解决**：
```python
# 在 .spec 文件中显式添加
hiddenimports=['bsdiff4', 'bsdiff4._bsdiff4']
```

### 问题 2: 增量更新变成完整更新

**原因**：程序检测不到 bsdiff4，自动降级

**解决**：
1. 检查虚拟环境是否安装了 bsdiff4
2. 重新编译，确保包含 bsdiff4
3. 查看日志，确认错误原因

### 问题 3: 补丁应用失败

**原因**：补丁文件损坏或版本不匹配

**解决**：
1. 验证补丁文件哈希
2. 确认旧版本文件哈希正确
3. 重新生成补丁

---

## 🎯 最佳实践

### 1. 显式声明依赖

```python
# XexunRTT_onefile_v2_2.spec
hiddenimports=[
    # 核心更新依赖
    'requests',
    'bsdiff4',
    'bsdiff4._bsdiff4',  # C扩展
    
    # 其他依赖
    'pylink',
    'serial',
    # ...
]
```

### 2. 优雅降级

```python
# 已在代码中实现
try:
    import bsdiff4
except ImportError:
    logger.error("bsdiff4 not available, using full update")
    # 自动降级到完整更新
```

### 3. 编译后验证

```bash
# 每次编译后测试
dist/XexunRTT.exe

# 检查日志中是否有 bsdiff4 错误
```

### 4. 文档说明

在发布说明中告知用户：
```
增量更新功能：
- 需要 bsdiff4 库（已内置）
- 自动节省 90% 流量
- 如果增量更新失败，会自动使用完整更新
```

---

## 📈 大小对比

### 包含 bsdiff4 的影响

| 项目 | 不含 bsdiff4 | 含 bsdiff4 | 增加 |
|------|-------------|-----------|------|
| **EXE 大小** | ~43 MB | ~43.2 MB | +200 KB |
| **运行内存** | ~80 MB | ~80 MB | 几乎无影响 |

**结论**：bsdiff4 非常轻量，对程序大小影响微乎其微（<0.5%），但能节省 90% 的更新流量！

---

## 🔄 服务器端也需要 bsdiff4

### 生成补丁时

```bash
# 服务器端生成补丁
python generate_patch.py 2.5 \
    --old-versions dist/XexunRTT_v2.4.exe \
    --new-file dist/XexunRTT_v2.5.exe

# 内部调用
import bsdiff4
patch_data = bsdiff4.diff(old_data, new_data)  # 👈 生成补丁
with open('patch.bsdiff', 'wb') as f:
    f.write(patch_data)
```

**服务器环境安装**：
```bash
pip install bsdiff4
```

---

## ✅ 总结

### Q: bsdiff4 是否需要集成在程序中？
**A: 是的，必须集成！**

### Q: 增量更新是否需要此库？
**A: 是的，必须需要！**

### 关键点

1. **客户端（打包的 EXE）**：
   - ✅ 必须包含 bsdiff4
   - ✅ 用于应用补丁
   - ✅ 如果缺失，自动降级到完整更新

2. **服务器端（生成补丁）**：
   - ✅ 必须安装 bsdiff4
   - ✅ 用于生成补丁

3. **大小影响**：
   - ✅ 仅增加 ~200 KB
   - ✅ 但能节省 90% 更新流量

4. **安全保障**：
   - ✅ 优雅降级机制
   - ✅ 不影响完整更新功能
   - ✅ 用户体验无缝

### 验证方法

```bash
# 1. 检查开发环境
pip list | grep bsdiff4

# 2. 检查 requirements.txt
cat requirements.txt | grep bsdiff4

# 3. 检查 .spec 文件
cat *.spec | grep bsdiff4

# 4. 运行时测试
python -c "import bsdiff4; print('OK')"

# 5. 打包后测试
dist/XexunRTT.exe  # 尝试增量更新
```

### 当前状态

- ✅ `requirements.txt` 已包含：`bsdiff4>=1.2.0`
- ✅ 代码已实现优雅降级
- ✅ 延迟导入，不影响启动速度
- ✅ 准备就绪，可以直接使用！

**您的程序已经正确配置了 bsdiff4！** 🎉

