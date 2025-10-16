# Git提交辅助脚本 - 解决中文乱码问题
# 使用方法: .\\.git-commit-helper.ps1 "提交信息"

param(
    [Parameter(Mandatory=$true)]
    [string]$Message
)

# 设置UTF-8编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

# 创建临时提交信息文件
$tempFile = Join-Path $PSScriptRoot ".git-commit-msg.tmp"
$Message | Out-File -FilePath $tempFile -Encoding UTF8 -NoNewline

try {
    # 使用文件方式提交
    git commit -F $tempFile
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ 提交成功" -ForegroundColor Green
    } else {
        Write-Host "❌ 提交失败" -ForegroundColor Red
    }
} finally {
    # 清理临时文件
    if (Test-Path $tempFile) {
        Remove-Item $tempFile -Force
    }
}

