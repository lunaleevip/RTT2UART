# JLink 设备数据库说明

## 文件信息

### JLinkDevicesBuildIn.xml
- **用途**: JLink 完整设备支持列表
- **大小**: ~2.45 MB
- **设备数**: ~8829 个设备
- **厂商**: Nordic, STMicroelectronics, NXP, Microchip, Infineon, Texas Instruments 等
- **包含**: ✅ 完整的 nRF52 系列（nRF52840, nRF52833, nRF52832 等）

## 数据库架构

### 主数据库 + 用户扩展

程序采用**两层数据库架构**：

1. **主数据库** (`JLinkDevicesBuildIn.xml`)
   - 包含官方完整的8829个设备
   - 优先从项目内置/JLink安装目录加载
   
2. **用户扩展数据库** (`JLinkDevices.xml` in 配置目录) ✨
   - 用户自定义设备
   - 自动合并到主数据库
   - 避免重复定义

## 加载优先级

程序按以下顺序查找设备数据库：

### 1. **项目内置数据库**（最高优先级）✨
```
位置：
  - PyInstaller 打包后：sys._MEIPASS/JLinkDevicesBuildIn.xml
  - 开发环境：项目根目录/JLinkDevicesBuildIn.xml
  - 可执行文件目录：exe所在目录/JLinkDevicesBuildIn.xml
  
优势：
  ✅ 独立于系统JLink安装
  ✅ 确保打包后正常工作
  ✅ 版本一致性，不受JLink更新影响
```

### 2. **JLink 安装目录**（次优先级）
```
位置：
  - C:\Program Files\SEGGER\JLink\JLinkDevicesBuildIn.xml
  - C:\Program Files\SEGGER\JLink\JLinkDevices.xml（用户自定义）
  - 通过 pylink 库自动查找
  - 通过注册表查找
  
优势：
  ✅ 获取最新的官方设备列表
  ✅ 支持新发布的芯片
```

### 3. **动态导出**（最后备用）
```
方式：
  - JLink.exe -ExpDevList 命令导出
  
要求：
  ⚠ 需要 JLink V7.80+ 版本
  ⚠ 仅在前两种方式失败时使用
```

## 打包配置

### XexunRTT_onefile_win.spec

数据库文件已配置在第58行：

```python
datas=[
    ('lang/xexunrtt_zh_CN.qm', 'lang'),
    ('lang/xexunrtt_zh_TW.qm', 'lang'),
    ('qt_zh_CN.qm', '.'),
    ('qt_zh_TW.qm', '.'),
    ('JLinkDevicesBuildIn.xml', '.'),  # ← JLink设备数据库
    ('JLinkCommandFile.jlink', '.'),
    ('ui/*.ui', 'ui'),
],
```

### 打包命令

```powershell
# 使用统一构建脚本（推荐）
python build.py

# 或直接使用 PyInstaller
pyinstaller XexunRTT_onefile_win.spec --clean
```

### 验证打包结果

打包后的EXE运行时，查看日志：

```
📦 Found built-in device database [_MEIPASS]: C:\Users\...\AppData\Local\Temp\_MEI...\JLinkDevicesBuildIn.xml
✅ Loaded built-in JLinkDevicesBuildIn.xml: 2452173 bytes, ~8829 devices
```

## 用户自定义设备 ✨

### 创建用户设备列表

**位置**:
- Windows: `%APPDATA%\XexunRTT\JLinkDevices.xml`
- macOS: `~/Library/Application Support/XexunRTT/JLinkDevices.xml`
- Linux: `~/.config/XexunRTT/JLinkDevices.xml`

**步骤**:

1. **复制示例文件**
   ```powershell
   # Windows
   $configDir = "$env:APPDATA\XexunRTT"
   New-Item -ItemType Directory -Force -Path $configDir
   Copy-Item "JLinkDevices_user_example.xml" -Destination "$configDir\JLinkDevices.xml"
   ```

2. **编辑设备列表**
   - 打开 `JLinkDevices.xml`
   - 添加您的自定义设备
   - 设置设备名称、RAM地址、RAM大小等

3. **重启程序**
   - 自动加载并合并用户设备
   - 查看日志确认：
   ```
   👤 Found user-defined device database: C:\Users\...\AppData\Roaming\XexunRTT\JLinkDevices.xml
   ✅ Loaded user devices: 1234 bytes, ~3 devices
   Merging databases: Main=8829 devices, User=3 devices
   ✅ Database merge complete: Added 3, Skipped 0 duplicates
      Total devices: 8832
   ```

### 设备定义格式

**格式1: VendorInfo/DeviceInfo（推荐）**

```xml
<VendorInfo Name="MyCompany">
  <DeviceInfo 
    Name="MyDevice_M4" 
    WorkRAMStartAddr="0x20000000" 
    WorkRAMSize="0x00040000"
    Core="JLINK_CORE_CORTEX_M4">
    <AliasInfo Name="MyDevice_Variant1"/>
  </DeviceInfo>
</VendorInfo>
```

**格式2: Device/ChipInfo（新格式）**

```xml
<Device>
  <ChipInfo 
    Name="MyAdvancedDevice"
    WorkRAMAddr="0x20000000"
    WorkRAMSize="0x00010000"
    Core="JLINK_CORE_CORTEX_M4"/>
</Device>
```

### 常用参数

**核心类型**:
- `JLINK_CORE_CORTEX_M0/M0PLUS`
- `JLINK_CORE_CORTEX_M3/M4/M7`
- `JLINK_CORE_CORTEX_M23/M33`

**RAM大小换算**:
```
8KB   = 0x00002000    256KB = 0x00040000
16KB  = 0x00004000    512KB = 0x00080000
32KB  = 0x00008000    1MB   = 0x00100000
64KB  = 0x00010000    2MB   = 0x00200000
128KB = 0x00020000
```

### 重复设备处理

- 如果用户设备与主数据库重复（相同Name），自动跳过用户设备
- 这确保官方定义优先，避免错误配置
- 日志会显示跳过的重复设备数量

## 更新主数据库

### 方式1: 从JLink安装目录复制（推荐）

```powershell
# 复制官方最新数据库
Copy-Item "C:\Program Files\SEGGER\JLink\JLinkDevicesBuildIn.xml" -Destination "JLinkDevicesBuildIn.xml" -Force

# 如果没有BuildIn版本，复制用户列表
Copy-Item "C:\Program Files\SEGGER\JLink\JLinkDevices.xml" -Destination "JLinkDevicesBuildIn.xml" -Force
```

### 方式2: 使用导出脚本

```powershell
python export_device_database.py
```

脚本会自动：
1. 尝试使用 `JLink.exe -ExpDevList` 导出
2. 失败则从安装目录复制
3. 显示文件大小和设备数量

### 验证更新结果

```powershell
python test_database_load.py
```

预期输出：
```
Testing JLink Device Database loading...
============================================================
✅ Database loaded successfully!
   Size: 2,452,173 bytes
   Devices: ~8829
   ✅ Contains nRF52840!
   Nordic devices: 1 references
```

## nRF52系列支持

### 包含的nRF52设备

数据库包含完整的Nordic nRF52系列：

- **nRF52840**: 256KB RAM, 1024KB Flash
- **nRF52833**: 128KB RAM, 512KB Flash
- **nRF52832**: 64KB RAM, 512KB Flash
- **nRF52811**: 24KB RAM, 192KB Flash
- **nRF52810**: 24KB RAM, 192KB Flash
- **nRF52805**: 24KB RAM, 192KB Flash

### RAM规格默认值

即使数据库查询失败，程序也有内置的准确RAM规格（`main_window.py` 第8590-8617行）：

```python
if 'nRF52840' in target_device:
    ram_start = 0x20000000
    ram_size = 256 * 1024  # 256KB
```

这确保F9重启功能的RAM格式化功能始终可用！

## 故障排查

### 问题1: 程序启动时提示"Can not find device database"

**原因**: 所有加载方式都失败

**解决**:
1. 确保项目根目录有 `JLinkDevicesBuildIn.xml`
2. 运行 `python export_database_database.py` 重新导出
3. 检查 JLink 是否正确安装

### 问题2: 设备列表中找不到 nRF52840

**原因**: 加载了旧版或用户自定义的数据库

**解决**:
1. 查看启动日志，确认加载的文件
2. 升级 JLink 到最新版本
3. 重新导出数据库: `python export_device_database.py`

### 问题3: 打包后的EXE无法加载数据库

**原因**: 数据库文件未打包进EXE

**检查**:
1. 确认 `.spec` 文件中有 `('JLinkDevicesBuildIn.xml', '.')`
2. 重新打包: `python build.py`
3. 使用解压工具查看EXE内容验证文件存在

### 问题4: F9重启时提示"Cannot determine RAM range"

**原因**: 设备不在数据库中且不在默认列表中

**解决**:
1. 升级数据库文件
2. 或在 `main_window.py` 第8590-8620行添加该设备的默认RAM配置

## 技术细节

### 代码位置

- **加载逻辑**: `main_window.py` 第535-720行 (`JLinkDeviceDatabaseDriver.get_xml_content`)
- **RAM查询**: `main_window.py` 第8360-8461行 (`_get_device_ram_info`)
- **默认RAM**: `main_window.py` 第8560-8620行 (`_format_ram_direct`)

### 日志标识

```python
# 内置数据库
📦 Found built-in device database [script_dir]: ...
✅ Loaded built-in JLinkDevicesBuildIn.xml: ...

# JLink安装目录
📁 Found device database: ...
✅ Loaded JLinkDevicesBuildIn.xml: ...

# 动态导出
✅ Exported device list from JLink.exe: ...
```

## 维护建议

1. **定期更新**: 当升级JLink版本后，重新导出数据库
2. **版本控制**: 将 `JLinkDevicesBuildIn.xml` 加入 Git（虽然文件较大）
3. **测试验证**: 每次更新后运行 `python test_database_load.py`
4. **文档同步**: 更新本文档的文件大小和设备数量

---

**最后更新**: 2025-11-26  
**数据库版本**: JLink V7.80+ 完整设备列表  
**文件大小**: 2.45 MB  
**设备数量**: ~8829

