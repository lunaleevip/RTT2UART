#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动速度测试脚本
比较不同版本的启动时间
"""

import os
import time
import subprocess
import statistics
from pathlib import Path

def test_startup_time(exe_path, test_name, runs=3):
    """测试指定程序的启动时间"""
    print(f"\n🧪 测试 {test_name}")
    print(f"📁 路径: {exe_path}")
    
    if not Path(exe_path).exists():
        print(f"❌ 文件不存在: {exe_path}")
        return None
    
    times = []
    
    for i in range(runs):
        print(f"  🔄 第 {i+1}/{runs} 次测试...", end="", flush=True)
        
        start_time = time.time()
        
        try:
            # 启动程序并立即关闭
            process = subprocess.Popen(
                [exe_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # 等待程序完全启动（通过检查进程状态）
            time.sleep(2)  # 给程序时间初始化
            
            # 关闭程序
            process.terminate()
            process.wait(timeout=5)
            
            elapsed = time.time() - start_time
            times.append(elapsed)
            print(f" {elapsed:.2f}s")
            
        except Exception as e:
            print(f" ❌ 错误: {e}")
            return None
        
        # 等待清理
        time.sleep(1)
    
    avg_time = statistics.mean(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"  ⏱️ 平均启动时间: {avg_time:.2f}s")
    print(f"  📊 最快: {min_time:.2f}s, 最慢: {max_time:.2f}s")
    
    return avg_time

def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / 1024:.1f} KB"

def main():
    """主函数"""
    print("🚀 XexunRTT 启动速度对比测试")
    print("=" * 60)
    
    # 定义测试版本
    test_cases = [
        {
            'name': '目录模式版本（最快）',
            'path': 'dist/XexunRTT_Fast/XexunRTT.exe',
            'description': '分离文件，启动最快'
        },
        {
            'name': '优化单文件版本',
            'path': 'dist_fast/XexunRTT_Fast.exe',
            'description': '优化打包，体积小'
        },
        {
            'name': '标准单文件版本',
            'path': 'dist/XexunRTT.exe',
            'description': '标准打包，功能完整'
        }
    ]
    
    results = []
    
    for case in test_cases:
        file_path = Path(case['path'])
        
        print(f"\n{'='*60}")
        print(f"📦 {case['name']}")
        print(f"📝 说明: {case['description']}")
        
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"📏 文件大小: {format_size(size)}")
            
            # 测试启动时间
            startup_time = test_startup_time(str(file_path), case['name'])
            
            if startup_time is not None:
                results.append({
                    'name': case['name'],
                    'path': case['path'],
                    'size': size,
                    'startup_time': startup_time
                })
        else:
            print(f"❌ 文件不存在: {file_path}")
    
    # 显示对比结果
    if results:
        print(f"\n{'='*60}")
        print("📊 启动速度对比结果")
        print(f"{'='*60}")
        
        # 按启动时间排序
        results.sort(key=lambda x: x['startup_time'])
        
        print(f"{'版本':<20} {'大小':<12} {'启动时间':<10} {'性能评级'}")
        print("-" * 60)
        
        fastest_time = results[0]['startup_time']
        
        for i, result in enumerate(results):
            size_str = format_size(result['size'])
            time_str = f"{result['startup_time']:.2f}s"
            
            # 计算性能评级
            if i == 0:
                rating = "⚡⚡⚡⚡⚡"
            elif result['startup_time'] <= fastest_time * 1.5:
                rating = "⚡⚡⚡⚡"
            elif result['startup_time'] <= fastest_time * 2:
                rating = "⚡⚡⚡"
            else:
                rating = "⚡⚡"
            
            print(f"{result['name']:<20} {size_str:<12} {time_str:<10} {rating}")
        
        print(f"\n💡 推荐使用顺序:")
        for i, result in enumerate(results):
            print(f"  {i+1}. {result['name']} - {format_size(result['size'])}")
            
        print(f"\n🎯 启动优化效果:")
        if len(results) >= 2:
            improvement = (results[-1]['startup_time'] - results[0]['startup_time']) / results[-1]['startup_time'] * 100
            print(f"  最快版本比最慢版本快 {improvement:.1f}%")
            
            size_reduction = (results[-1]['size'] - results[0]['size']) / (1024 * 1024)
            if size_reduction > 0:
                print(f"  文件大小减少了 {size_reduction:.1f} MB")
    
    print(f"\n✅ 测试完成！")
    print(f"\n💡 解决EXE启动慢的方法:")
    print(f"  1. 使用目录模式 - 启动最快")
    print(f"  2. 使用优化单文件 - 体积小，启动较快")
    print(f"  3. 减少打包的模块 - 降低初始化时间")
    print(f"  4. 使用SSD硬盘 - 减少文件读取时间")

if __name__ == '__main__':
    main()
