# UTF-8 Environment Setup Script for XexunRTT Development
# This script sets up proper UTF-8 encoding for AI development environment

Write-Host "Setting up UTF-8 environment..." -ForegroundColor Green

# Set console code page to UTF-8
chcp 65001 | Out-Null

# Set Python IO encoding
$env:PYTHONIOENCODING = "utf-8"

# Set PowerShell output encoding
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Test encoding
Write-Host "UTF-8 encoding setup completed!" -ForegroundColor Green
Write-Host "Testing Python UTF-8 support..." -ForegroundColor Yellow

python -c "import sys; print(f'Python encoding: {sys.stdout.encoding}'); print('Test: UTF-8 works!')"

Write-Host "Environment ready for development." -ForegroundColor Green
