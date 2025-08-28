# PowerShell脚本 - 设置调试环境
Write-Host "设置RTT2UART调试环境..." -ForegroundColor Green

# 检查虚拟环境是否存在
if (Test-Path "env\Scripts\activate.bat") {
    Write-Host "虚拟环境已存在" -ForegroundColor Yellow
} else {
    Write-Host "创建虚拟环境..." -ForegroundColor Blue
    python -m venv env
}

# 激活虚拟环境
Write-Host "激活虚拟环境..." -ForegroundColor Blue
& .\env\Scripts\Activate.ps1

# 安装依赖
Write-Host "安装项目依赖..." -ForegroundColor Blue
pip install -r requirements.txt

# 显示环境信息
Write-Host "`n环境配置完成！" -ForegroundColor Green
Write-Host "Python版本：" -ForegroundColor Cyan
python --version
Write-Host "Python路径：" -ForegroundColor Cyan
Get-Command python | Select-Object Source

Write-Host "`n可用命令：" -ForegroundColor Yellow
Write-Host "1. 运行程序: python main_window.py" -ForegroundColor White
Write-Host "2. 激活环境: .\env\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "3. 退出环境: deactivate" -ForegroundColor White

