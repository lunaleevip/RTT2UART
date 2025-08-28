#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
性能优化测试脚本
对比优化前后的性能差异
"""

import time
import sys
import threading
from collections import deque
import random
import string

def simulate_data_processing_old():
    """模拟旧版本的数据处理逻辑"""
    buffers = [""] * 24
    
    start_time = time.time()
    
    # 模拟1000次数据处理
    for i in range(1000):
        # 模拟接收到的数据
        data = ''.join(random.choices(string.ascii_letters + string.digits, k=50)) + '\n'
        
        # 旧版本：每次都字符串拼接 + 文件I/O
        for j in range(24):
            buffers[j] += f"{i:02d}> {data}"
            
            # 模拟频繁文件写入
            with open(f'temp_log_{j}.log', 'a') as f:
                f.write(data)
        
        # 模拟GUI更新频率过高 (每10ms一次)
        if i % 10 == 0:
            time.sleep(0.001)  # 模拟GUI刷新延迟
    
    end_time = time.time()
    
    # 清理临时文件
    import os
    for j in range(24):
        try:
            os.remove(f'temp_log_{j}.log')
        except:
            pass
    
    return end_time - start_time

def simulate_data_processing_new():
    """模拟新版本的优化数据处理逻辑"""
    buffers = [""] * 24
    log_buffers = {}  # 文件缓冲
    dirty_flags = [False] * 24
    
    start_time = time.time()
    
    # 模拟1000次数据处理
    for i in range(1000):
        # 模拟接收到的数据
        data = ''.join(random.choices(string.ascii_letters + string.digits, k=50)) + '\n'
        
        # 新版本：优化的字符串处理
        for j in range(24):
            # 使用列表拼接替代字符串拼接
            buffer_parts = [f"{i:02d}> ", data]
            buffers[j] += ''.join(buffer_parts)
            
            # 标记需要更新
            dirty_flags[j] = True
            
            # 缓冲文件写入
            log_file = f'temp_log_{j}.log'
            if log_file not in log_buffers:
                log_buffers[log_file] = ""
            log_buffers[log_file] += data
        
        # 模拟优化的GUI更新频率 (每50ms一次，且智能更新)
        if i % 50 == 0:
            # 只更新有变化的页面，且限制数量
            updated_count = 0
            for j in range(24):
                if dirty_flags[j] and updated_count < 3:
                    dirty_flags[j] = False
                    updated_count += 1
            time.sleep(0.001)  # 模拟GUI刷新延迟
    
    # 模拟批量文件写入
    for log_file, content in log_buffers.items():
        with open(log_file, 'w') as f:
            f.write(content)
    
    end_time = time.time()
    
    # 清理临时文件
    import os
    for j in range(24):
        try:
            os.remove(f'temp_log_{j}.log')
        except:
            pass
    
    return end_time - start_time

def test_string_concatenation():
    """测试字符串拼接性能"""
    data = "test data " * 10
    iterations = 10000
    
    # 旧方法：直接字符串拼接
    start_time = time.time()
    result_old = ""
    for i in range(iterations):
        result_old += f"{i}: {data}\n"
    old_time = time.time() - start_time
    
    # 新方法：列表拼接
    start_time = time.time()
    result_parts = []
    for i in range(iterations):
        result_parts.extend([f"{i}: ", data, "\n"])
    result_new = ''.join(result_parts)
    new_time = time.time() - start_time
    
    return old_time, new_time

def test_file_io():
    """测试文件I/O性能"""
    data = "test data " * 10 + "\n"
    iterations = 1000
    
    # 旧方法：每次打开关闭文件
    import os
    start_time = time.time()
    for i in range(iterations):
        with open('temp_test_old.log', 'a') as f:
            f.write(data)
    old_time = time.time() - start_time
    
    # 新方法：缓冲写入
    start_time = time.time()
    buffer_content = ""
    for i in range(iterations):
        buffer_content += data
        if i % 100 == 0:  # 每100次写入一次
            with open('temp_test_new.log', 'a') as f:
                f.write(buffer_content)
            buffer_content = ""
    # 写入剩余内容
    if buffer_content:
        with open('temp_test_new.log', 'a') as f:
            f.write(buffer_content)
    new_time = time.time() - start_time
    
    # 清理
    try:
        os.remove('temp_test_old.log')
        os.remove('temp_test_new.log')
    except:
        pass
    
    return old_time, new_time

def run_performance_tests():
    """运行所有性能测试"""
    print("🧪 RTT2UART 性能优化测试")
    print("="*50)
    
    print("📊 测试1: 整体数据处理性能")
    print("   测试中...", end="", flush=True)
    old_time = simulate_data_processing_old()
    print("✓")
    print("   优化后测试中...", end="", flush=True)
    new_time = simulate_data_processing_new()
    print("✓")
    
    improvement = ((old_time - new_time) / old_time) * 100
    print(f"   旧版本耗时: {old_time:.3f}秒")
    print(f"   新版本耗时: {new_time:.3f}秒")
    print(f"   性能提升: {improvement:.1f}%")
    
    print(f"\n📊 测试2: 字符串拼接性能")
    print("   测试中...", end="", flush=True)
    old_str_time, new_str_time = test_string_concatenation()
    print("✓")
    
    str_improvement = ((old_str_time - new_str_time) / old_str_time) * 100
    print(f"   直接拼接: {old_str_time:.3f}秒")
    print(f"   列表拼接: {new_str_time:.3f}秒")
    print(f"   性能提升: {str_improvement:.1f}%")
    
    print(f"\n📊 测试3: 文件I/O性能")
    print("   测试中...", end="", flush=True)
    old_io_time, new_io_time = test_file_io()
    print("✓")
    
    io_improvement = ((old_io_time - new_io_time) / old_io_time) * 100
    print(f"   频繁I/O: {old_io_time:.3f}秒")
    print(f"   缓冲I/O: {new_io_time:.3f}秒")
    print(f"   性能提升: {io_improvement:.1f}%")
    
    print(f"\n🎯 总体评估:")
    avg_improvement = (improvement + str_improvement + io_improvement) / 3
    print(f"   平均性能提升: {avg_improvement:.1f}%")
    
    if avg_improvement > 30:
        print("   ✅ 优化效果显著")
    elif avg_improvement > 15:
        print("   🟡 优化效果中等")
    else:
        print("   ⚠️  优化效果有限")
    
    print(f"\n💡 优化建议:")
    print(f"   • GUI刷新频率从100ms降低到500ms")
    print(f"   • 采用智能页面更新策略")
    print(f"   • 使用文件I/O缓冲机制")
    print(f"   • 优化字符串拼接算法")
    print(f"   • 增加RTT读取缓冲区大小")
    
    print("="*50)

if __name__ == "__main__":
    run_performance_tests()

