# XexunRTT 差异化自动更新功能

## 🚀 快速开始

### 对于开发者 (部署更新)

#### 方式1: 使用交互式脚本 (推荐)

```bash
# Windows
quick_deploy.bat

# Linux/macOS
python deploy_update.py --interactive
```

按照提示输入信息即可。

#### 方式2: 命令行模式

```bash
python deploy_update.py \
    --new-version 2.3.0 \
    --new-file XexunRTT_v2.3.0.exe \
    --old-versions XexunRTT_v2.2.0.exe XexunRTT_v2.1.3.exe \
    --release-notes "修复了XX问题，新增了XX功能" \
    --output-dir ./updates
```

生成的文件会在 `./updates/` 目录中，然后上传到HTTP服务器。

---

### 对于用户 (使用自动更新)

**无需任何操作!** 程序启动时会自动检查更新:

1. 如果有新版本，会弹出更新对话框
2. 点击"立即更新"开始下载（自动选择增量更新）
3. 下载完成后，程序会自动重启并应用更新

---

## 📦 文件说明

| 文件 | 用途 | 使用者 |
|------|------|--------|
| `auto_updater.py` | 更新核心逻辑 | 已集成到程序 |
| `update_dialog.py` | 更新UI界面 | 已集成到程序 |
| `generate_patch.py` | 生成补丁工具 | 开发者 |
| `deploy_update.py` | 快速部署脚本 | 开发者 |
| `quick_deploy.bat` | Windows快速部署 | 开发者 |
| `AUTO_UPDATE_GUIDE.md` | 详细文档 | 开发者/管理员 |
| `version_example.json` | 配置示例 | 参考 |

---

## 🔧 配置

### 修改服务器地址

编辑 `auto_updater.py`:

```python
UPDATE_SERVER = "http://your-domain.com/xexunrtt/updates"
```

### 服务器目录结构

```
/var/www/html/xexunrtt/updates/
├── version.json                      # 版本信息
├── XexunRTT_v2.3.0.exe              # 最新版本
└── patch_2.2.0_to_2.3.0.patch       # 差异补丁
```

---

## 💡 工作原理

### 增量更新优势

假设程序大小为 45 MB:

- **完整更新**: 下载 45 MB
- **增量更新**: 只下载 3-5 MB（节省 89-93% 流量）

### 更新流程

```
客户端启动 → 检查版本 → 发现更新 → 下载补丁 
→ 应用补丁 → 验证哈希 → 替换文件 → 重启程序
```

---

## 📊 效果对比

| 场景 | 完整下载 | 增量更新 | 节省 |
|------|---------|---------|------|
| 小改动(bug fix) | 45 MB | 2-3 MB | 93-95% |
| 中等改动(新功能) | 45 MB | 5-8 MB | 82-89% |
| 大改动(重构) | 45 MB | 15-20 MB | 56-67% |

---

## ⚠️ 注意事项

1. **首次部署**: 需要手动上传完整exe和version.json
2. **补丁策略**: 建议保留最近2-3个版本的补丁
3. **安全性**: 生产环境请使用HTTPS
4. **备份**: 系统会自动保留.exe.old备份文件

---

## 🐛 故障排除

### 问题: bsdiff4 安装失败

```bash
pip install --upgrade pip
pip install bsdiff4
```

### 问题: 更新失败

1. 检查网络连接
2. 查看日志文件
3. 手动下载完整版本
4. 使用备份文件恢复: `copy XexunRTT.exe.old XexunRTT.exe`

---

## 📚 相关文档

- [详细使用指南](AUTO_UPDATE_GUIDE.md) - 完整的技术文档
- [示例配置](version_example.json) - version.json模板

---

## 🎉 完成

现在您可以:

✅ 快速部署新版本更新  
✅ 为用户提供增量更新，节省流量  
✅ 自动化版本管理流程  

**开始使用**: 运行 `quick_deploy.bat` 或查看 [详细文档](AUTO_UPDATE_GUIDE.md)

