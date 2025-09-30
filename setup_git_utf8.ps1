# Git UTF-8 Configuration Script
# This script configures Git to properly handle UTF-8 encoding

Write-Host "Configuring Git for UTF-8 encoding..." -ForegroundColor Green

# Set console to UTF-8
chcp 65001 | Out-Null

# Set PowerShell encoding
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Set environment variables for UTF-8
$env:PYTHONIOENCODING = "utf-8"
$env:LC_ALL = "en_US.UTF-8"
$env:LANG = "en_US.UTF-8"

# Configure Git for UTF-8
git config --global core.quotepath false
git config --global i18n.commitencoding utf-8
git config --global i18n.logoutputencoding utf-8
git config --global core.precomposeunicode true

Write-Host "Git UTF-8 configuration completed!" -ForegroundColor Green

# Test Git log display
Write-Host "Testing Git log display..." -ForegroundColor Yellow
git log --oneline -3
