#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动更新模块 - 支持差异化更新
使用 BSDiff 算法实现增量更新,只下载差异部分
"""

import os
import sys
import json
import hashlib
import requests
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

# 配置
# 生产服务器地址 - 最终发布时使用（根据平台自动选择）
def _get_platform_server():
    """根据平台返回对应的服务器地址"""
    import sys
    base_url = "http://sz.xexun.com:18891/uploads/xexunrtt/updates"
    
    if sys.platform == "win32":
        return f"{base_url}/win"
    elif sys.platform == "darwin":
        return f"{base_url}/macos"
    elif sys.platform.startswith("linux"):
        return f"{base_url}/linux"
    else:
        return f"{base_url}/win"  # 默认使用Windows

PRODUCTION_SERVER = _get_platform_server()

# 测试服务器地址 - 本地测试时使用
TEST_SERVER = "http://127.0.0.1:8888"

# 配置文件路径
UPDATE_CONFIG_FILE = Path(__file__).parent / "update_config.ini"

VERSION_FILE = "version.json"  # 版本信息文件

# 从 version.py 读取当前版本
try:
    from version import VERSION
    CURRENT_VERSION = VERSION
except ImportError:
    CURRENT_VERSION = "2.4"  # 备用版本号


def get_update_server() -> str:
    """
    获取更新服务器地址
    
    优先级:
    1. update_config.ini 文件中的配置
    2. 环境变量 XEXUNRTT_UPDATE_SERVER
    3. 默认生产服务器地址
    
    Returns:
        服务器URL
    """
    # 1. 检查配置文件
    if UPDATE_CONFIG_FILE.exists():
        try:
            with open(UPDATE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('server='):
                        server = line.split('=', 1)[1].strip()
                        logger.info(f"Using update server from config: {server}")
                        return server
        except Exception as e:
            logger.warning(f"Failed to read update config: {e}")
    
    # 2. 检查环境变量
    env_server = os.environ.get('XEXUNRTT_UPDATE_SERVER')
    if env_server:
        logger.info(f"Using update server from environment: {env_server}")
        return env_server
    
    # 3. 使用默认生产服务器
    logger.info(f"Using default production server: {PRODUCTION_SERVER}")
    return PRODUCTION_SERVER


class AutoUpdater:
    """自动更新器"""
    
    def __init__(self, server_url: str = None):
        """
        初始化更新器
        
        Args:
            server_url: 更新服务器URL (可选，默认使用配置文件或环境变量)
        """
        if server_url is None:
            server_url = get_update_server()
        
        self.server_url = server_url.rstrip('/')
        self.current_exe = self._get_current_exe()
        self.current_version = CURRENT_VERSION
        
    def _get_current_exe(self) -> Path:
        """获取当前可执行文件路径"""
        if getattr(sys, 'frozen', False):
            # 打包后的exe
            return Path(sys.executable)
        else:
            # 开发环境
            return Path(__file__).parent / "XexunRTT.exe"
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件SHA256哈希
        
        Args:
            file_path: 文件路径
            
        Returns:
            SHA256哈希值
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _verify_current_file_integrity(self, current_hash: str, 
                                       current_version: str, 
                                       server_info: Dict) -> str:
        """
        验证当前文件完整性
        
        通过对比当前文件的哈希值与服务器记录的哈希值来检测文件是否被篡改
        
        Args:
            current_hash: 当前文件的SHA256哈希
            current_version: 当前版本号
            server_info: 服务器返回的版本信息
            
        Returns:
            "verified" - 完整性验证通过
            "modified" - 文件被修改/篡改
            "unknown" - 无法验证（服务器无记录）
        """
        # 1. 检查当前版本是否是最新版本
        if current_version == server_info.get('version'):
            expected_hash = server_info.get('hash')
            if current_hash == expected_hash:
                return "verified"
            else:
                return "modified"
        
        # 2. 检查历史版本记录
        history = server_info.get('history', [])
        for hist_entry in history:
            if hist_entry.get('version') == current_version:
                expected_hash = hist_entry.get('hash')
                if expected_hash and current_hash == expected_hash:
                    return "verified"
                else:
                    return "modified"
        
        # 3. 检查补丁记录中的源版本哈希
        patches = server_info.get('patches', {})
        for patch_key, patch_info in patches.items():
            # 补丁key格式: "2.2.0_2.3.0"
            if patch_info.get('from_version') == current_version:
                # 如果有源文件哈希记录
                if 'from_hash' in patch_info:
                    expected_hash = patch_info['from_hash']
                    if current_hash == expected_hash:
                        return "verified"
                    else:
                        return "modified"
        
        # 4. 无法验证（服务器没有该版本的哈希记录）
        logger.warning(f"No hash record found for version {current_version}")
        return "unknown"
    
    def check_for_updates(self) -> Optional[Dict]:
        """
        检查是否有更新
        
        增强安全性:
        1. 首先验证当前文件完整性（检测是否被篡改）
        2. 然后比较版本号
        3. 最后查找可用的补丁
        
        Returns:
            更新信息字典,如果没有更新返回None
            {
                'version': '2.3.0',
                'hash': 'sha256...',
                'size': 12345678,
                'patch_url': 'http://...',  # 差异补丁URL
                'full_url': 'http://...',   # 完整文件URL (备用)
                'patch_size': 123456,       # 补丁大小
                'release_notes': '更新内容...'
            }
        """
        try:
            # 1. 获取服务器上的版本信息
            version_url = f"{self.server_url}/{VERSION_FILE}"
            logger.info(f"Checking for updates from: {version_url}")
            
            response = requests.get(version_url, timeout=10)
            response.raise_for_status()
            
            server_info = response.json()
            
            # 2. 验证当前文件完整性（防篡改检测）
            current_hash = self._calculate_file_hash(self.current_exe)
            logger.info(f"Current file hash: {current_hash[:16]}...")
            
            integrity_check = self._verify_current_file_integrity(
                current_hash, 
                self.current_version, 
                server_info
            )
            
            if integrity_check == "modified":
                # 文件被修改，强制完整更新
                logger.warning("⚠️  Current file has been modified! Forcing full update.")
                logger.warning(f"   Expected hash for v{self.current_version} not found in server records")
                logger.warning(f"   Current hash: {current_hash}")
                
                # 提示用户文件可能被篡改
                server_version = server_info.get('version', '')
                return {
                    'version': server_version,
                    'hash': server_info['hash'],
                    'size': server_info['size'],
                    'full_url': f"{self.server_url}/{server_info['file']}",
                    'release_notes': server_info.get('release_notes', ''),
                    'update_type': 'full',
                    'integrity_warning': True,  # 标记完整性警告
                    'current_hash': current_hash
                }
            elif integrity_check == "verified":
                logger.info("✅ Current file integrity verified")
            
            # 3. 比较版本号
            server_version = server_info.get('version', '')
            
            # 如果版本号相同，进一步检查哈希值
            if self._compare_versions(server_version, self.current_version) == 0:
                # 版本号相同，检查哈希是否一致
                if current_hash == server_info.get('hash'):
                    logger.info(f"No update needed. Current version and hash match.")
                    return None
                else:
                    # 版本号相同但哈希不同，说明文件被修改，需要修复
                    logger.warning(f"⚠️  Version matches but hash differs! File may be corrupted.")
                    logger.warning(f"   Current: {current_hash[:16]}...")
                    logger.warning(f"   Expected: {server_info.get('hash', '')[:16]}...")
                    return {
                        'version': server_version,
                        'hash': server_info['hash'],
                        'size': server_info['size'],
                        'full_url': f"{self.server_url}/{server_info['file']}",
                        'release_notes': "文件完整性校验失败，需要修复",
                        'update_type': 'full',
                        'integrity_warning': True,
                        'is_repair': True  # 标记为修复更新
                    }
            
            if self._compare_versions(server_version, self.current_version) < 0:
                logger.info(f"No update needed. Current: {self.current_version}, Server: {server_version}")
                return None
            
            # 4. 检查是否有可用的差异补丁
            patches = server_info.get('patches', {})
            
            # 查找从当前版本到最新版本的补丁
            patch_key = f"{self.current_version}_{server_version}"
            if patch_key in patches:
                patch_info = patches[patch_key]
                logger.info(f"Found patch from {self.current_version} to {server_version}")
                logger.info(f"Patch size: {patch_info['size']} bytes (vs full: {server_info['size']} bytes)")
                
                return {
                    'version': server_version,
                    'hash': server_info['hash'],
                    'size': server_info['size'],
                    'patch_url': f"{self.server_url}/{patch_info['file']}",
                    'full_url': f"{self.server_url}/{server_info['file']}",
                    'patch_size': patch_info['size'],
                    'release_notes': server_info.get('release_notes', ''),
                    'update_type': 'patch'
                }
            else:
                # 没有差异补丁,需要下载完整文件
                logger.warning(f"No patch available from {self.current_version} to {server_version}")
                logger.info("Will download full version")
                
                return {
                    'version': server_version,
                    'hash': server_info['hash'],
                    'size': server_info['size'],
                    'full_url': f"{self.server_url}/{server_info['file']}",
                    'release_notes': server_info.get('release_notes', ''),
                    'update_type': 'full'
                }
                
        except requests.RequestException as e:
            logger.error(f"Failed to check for updates: {e}")
            return None
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None
    
    def download_and_apply_update(self, update_info: Dict, 
                                   progress_callback=None) -> bool:
        """
        下载并应用更新
        
        Args:
            update_info: 更新信息字典
            progress_callback: 进度回调函数 callback(current, total, status)
            
        Returns:
            是否成功
        """
        try:
            if update_info['update_type'] == 'patch':
                return self._apply_patch_update(update_info, progress_callback)
            else:
                return self._apply_full_update(update_info, progress_callback)
                
        except Exception as e:
            logger.error(f"Failed to apply update: {e}")
            return False
    
    def _apply_patch_update(self, update_info: Dict, 
                           progress_callback=None) -> bool:
        """
        应用差异补丁更新
        
        Args:
            update_info: 更新信息
            progress_callback: 进度回调
            
        Returns:
            是否成功
        """
        try:
            import bsdiff4
        except ImportError:
            logger.error("bsdiff4 not installed. Falling back to full update.")
            update_info['update_type'] = 'full'
            return self._apply_full_update(update_info, progress_callback)
        
        temp_dir = None
        try:
            # 1. 下载补丁文件
            if progress_callback:
                progress_callback(0, 100, "正在下载更新补丁...")
            
            temp_dir = Path(tempfile.mkdtemp())
            patch_file = temp_dir / "update.patch"
            
            self._download_file(update_info['patch_url'], patch_file, 
                              update_info['patch_size'], progress_callback)
            
            # 2. 应用补丁
            if progress_callback:
                progress_callback(0, 100, "正在应用更新补丁...")
            
            new_exe = temp_dir / "XexunRTT_new.exe"
            
            # 读取当前文件
            with open(self.current_exe, 'rb') as f:
                old_data = f.read()
            
            # 读取补丁
            with open(patch_file, 'rb') as f:
                patch_data = f.read()
            
            # 应用补丁
            new_data = bsdiff4.patch(old_data, patch_data)
            
            # 写入新文件
            with open(new_exe, 'wb') as f:
                f.write(new_data)
            
            # 3. 验证哈希
            if progress_callback:
                progress_callback(0, 100, "正在验证文件完整性...")
            
            new_hash = self._calculate_file_hash(new_exe)
            if new_hash != update_info['hash']:
                raise ValueError("Hash verification failed after patching")
            
            # 4. 替换旧文件
            if progress_callback:
                progress_callback(0, 100, "正在安装更新...")
            
            return self._replace_exe(new_exe)
            
        finally:
            # 清理临时文件
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")
    
    def _apply_full_update(self, update_info: Dict, 
                          progress_callback=None) -> bool:
        """
        应用完整更新
        
        Args:
            update_info: 更新信息
            progress_callback: 进度回调
            
        Returns:
            是否成功
        """
        temp_dir = None
        try:
            # 1. 下载完整文件
            if progress_callback:
                progress_callback(0, 100, "正在下载更新文件...")
            
            temp_dir = Path(tempfile.mkdtemp())
            new_exe = temp_dir / "XexunRTT_new.exe"
            
            self._download_file(update_info['full_url'], new_exe,
                              update_info['size'], progress_callback)
            
            # 2. 验证哈希
            if progress_callback:
                progress_callback(0, 100, "正在验证文件完整性...")
            
            new_hash = self._calculate_file_hash(new_exe)
            if new_hash != update_info['hash']:
                raise ValueError("Hash verification failed")
            
            # 3. 替换旧文件
            if progress_callback:
                progress_callback(0, 100, "正在安装更新...")
            
            return self._replace_exe(new_exe)
            
        finally:
            # 清理临时文件
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")
    
    def _download_file(self, url: str, dest: Path, total_size: int,
                      progress_callback=None):
        """
        下载文件并显示进度
        
        Args:
            url: 下载URL
            dest: 目标路径
            total_size: 文件总大小
            progress_callback: 进度回调
        """
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        downloaded = 0
        chunk_size = 8192
        
        with open(dest, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if progress_callback and total_size > 0:
                        progress = int(downloaded * 100 / total_size)
                        status = f"已下载 {self._format_size(downloaded)} / {self._format_size(total_size)}"
                        progress_callback(progress, 100, status)
    
    def _replace_exe(self, new_exe: Path) -> bool:
        """
        替换可执行文件
        
        Args:
            new_exe: 新的exe路径
            
        Returns:
            是否成功
        """
        try:
            # Windows下需要使用批处理脚本来替换正在运行的exe
            if sys.platform == 'win32':
                return self._replace_exe_windows(new_exe)
            else:
                # macOS/Linux 可以直接替换
                backup = self.current_exe.with_suffix('.exe.old')
                if backup.exists():
                    backup.unlink()
                shutil.copy2(self.current_exe, backup)
                shutil.copy2(new_exe, self.current_exe)
                os.chmod(self.current_exe, 0o755)
                return True
                
        except Exception as e:
            logger.error(f"Failed to replace exe: {e}")
            return False
    
    def _replace_exe_windows(self, new_exe: Path) -> bool:
        """
        Windows下替换exe
        
        创建批处理脚本,在程序退出后执行替换
        """
        try:
            # 创建更新脚本
            script_path = self.current_exe.parent / "_update.bat"
            
            script_content = f"""@echo off
echo Waiting for application to close...
timeout /t 2 /nobreak > nul

echo Backing up old version...
if exist "{self.current_exe}.old" del /f "{self.current_exe}.old"
move /y "{self.current_exe}" "{self.current_exe}.old"

echo Installing new version...
move /y "{new_exe}" "{self.current_exe}"

echo Update completed!
timeout /t 2 /nobreak > nul

echo Starting application...
start "" "{self.current_exe}"

echo Cleaning up...
timeout /t 2 /nobreak > nul
del /f "%~f0"
"""
            
            with open(script_path, 'w', encoding='gbk') as f:
                f.write(script_content)
            
            # 启动更新脚本
            import subprocess
            subprocess.Popen([str(script_path)], 
                           creationflags=subprocess.CREATE_NEW_CONSOLE,
                           shell=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create update script: {e}")
            return False
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """
        比较版本号
        
        Args:
            v1: 版本1
            v2: 版本2
            
        Returns:
            1 if v1 > v2, 0 if equal, -1 if v1 < v2
        """
        try:
            parts1 = [int(x) for x in v1.split('.')]
            parts2 = [int(x) for x in v2.split('.')]
            
            # 补齐长度
            max_len = max(len(parts1), len(parts2))
            parts1 += [0] * (max_len - len(parts1))
            parts2 += [0] * (max_len - len(parts2))
            
            for p1, p2 in zip(parts1, parts2):
                if p1 > p2:
                    return 1
                elif p1 < p2:
                    return -1
            
            return 0
            
        except Exception:
            # 如果解析失败,使用字符串比较
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
            else:
                return 0
    
    @staticmethod
    def _format_size(size: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


# 使用示例
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    updater = AutoUpdater()
    
    # 检查更新
    update_info = updater.check_for_updates()
    
    if update_info:
        print(f"发现新版本: {update_info['version']}")
        print(f"更新类型: {update_info['update_type']}")
        
        if update_info['update_type'] == 'patch':
            print(f"补丁大小: {AutoUpdater._format_size(update_info['patch_size'])}")
            print(f"完整大小: {AutoUpdater._format_size(update_info['size'])}")
            ratio = (1 - update_info['patch_size'] / update_info['size']) * 100
            print(f"节省流量: {ratio:.1f}%")
        else:
            print(f"文件大小: {AutoUpdater._format_size(update_info['size'])}")
        
        print(f"\n更新内容:\n{update_info['release_notes']}")
        
        # 下载并应用更新
        def progress(current, total, status):
            print(f"\r进度: {current}% - {status}", end='', flush=True)
        
        if updater.download_and_apply_update(update_info, progress):
            print("\n\n更新成功!程序将重新启动...")
        else:
            print("\n\n更新失败!")
    else:
        print("当前已是最新版本")

