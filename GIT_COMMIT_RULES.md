# Git提交规则 - 防止中文乱码

## 问题说明

在Windows PowerShell中，直接使用 `git commit -m "中文消息"` 会导致提交信息乱码。

**错误示例：**
```powershell
git commit -m "修复：某个功能"  # ❌ 会乱码
```

## 正确方法

### 方法1：使用辅助脚本（推荐）

```powershell
# 使用项目提供的辅助脚本
.\\.git-commit-helper.ps1 "修复：某个功能"
```

### 方法2：使用临时文件

```powershell
# 1. 创建UTF-8编码的提交信息文件
"修复：某个功能" | Out-File -FilePath commit_msg.txt -Encoding UTF8 -NoNewline

# 2. 使用文件提交
git commit -F commit_msg.txt

# 3. 清理临时文件
Remove-Item commit_msg.txt
```

### 方法3：使用Git GUI工具

- 使用 VS Code 的 Source Control 面板
- 使用 GitHub Desktop
- 使用 TortoiseGit

## AI助手规则

当AI助手需要执行git commit时，**必须**遵循以下规则：

1. ❌ **禁止**直接使用 `git commit -m "中文消息"`
2. ✅ **必须**先将提交信息写入UTF-8编码的文件
3. ✅ **必须**使用 `git commit -F 文件名` 方式提交
4. ✅ 提交后删除临时文件

**标准模板：**

```powershell
# 步骤1：创建UTF-8提交信息文件
$msg = @"
提交标题

- 修改点1
- 修改点2
"@
$msg | Out-File -FilePath .git-commit-msg.tmp -Encoding UTF8 -NoNewline

# 步骤2：使用文件提交
git commit -F .git-commit-msg.tmp

# 步骤3：清理临时文件
Remove-Item .git-commit-msg.tmp -Force
```

## 配置Git

可以设置Git的编码配置（可选）：

```bash
git config --global core.quotepath false
git config --global gui.encoding utf-8
git config --global i18n.commit.encoding utf-8
git config --global i18n.logoutputencoding utf-8
```

## 验证提交信息

提交后验证是否正确：

```powershell
git log --oneline -1  # 查看最后一次提交
```

如果出现乱码，使用以下命令修复：

```powershell
# 撤销最后一次提交（保留更改）
git reset --soft HEAD~1

# 使用正确方法重新提交
.\\.git-commit-helper.ps1 "正确的提交信息"
```

## 注意事项

- PowerShell ISE 和 PowerShell Core 的编码行为可能不同
- Windows Terminal 默认使用UTF-8，但PowerShell脚本中的编码需要显式设置
- `chcp 65001` 在PowerShell脚本中不总是有效
- 文件方式（`-F`）是最可靠的方法

## 相关文件

- `.git-commit-helper.ps1` - 提交辅助脚本
- `.gitignore` - 已配置忽略 `.git-commit-msg.tmp`

