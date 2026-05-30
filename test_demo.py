#!/usr/bin/env python3
"""
工业级分块下载系统 - 演示脚本
"""

import os
import sys
import shutil
import hashlib
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from server import IndustrialChunkServer
from client import LocalChunkClient


def create_test_file(path: str, size_kb: int = 100):
    """创建测试文件"""
    content = "测试数据 " * (size_kb * 64)  # 约1KB每行
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return os.path.getsize(path)


def calculate_file_hash(path: str) -> str:
    """计算文件哈希"""
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    print("="*70)
    print("  工业级分块下载系统 - 演示")
    print("="*70)
    
    # 测试参数
    test_file = "test_file_demo.txt"
    chunk_size = 1024  # 1KB（便于演示）
    output_dir = "test_chunks"
    restored_file = "test_file_restored.txt"
    
    # 清理旧文件
    print("\n[1/4] 清理旧文件...")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    if os.path.exists(restored_file):
        os.remove(restored_file)
    if os.path.exists(test_file):
        os.remove(test_file)
    
    # 创建测试文件
    print(f"\n[2/4] 创建测试文件 ({chunk_size*100} KB)...")
    file_size = create_test_file(test_file, chunk_size * 100)
    original_hash = calculate_file_hash(test_file)
    print(f"  文件大小: {file_size:,} 字节")
    print(f"  文件哈希: {original_hash}")
    
    # 服务端分块
    print(f"\n[3/4] 服务端分块 (分块大小: {chunk_size} 字节)...")
    server = IndustrialChunkServer(chunk_size=chunk_size, workers=4)
    config = server.split_file(test_file, output_dir)
    server.print_summary(config)
    
    # 客户端合并
    print(f"\n[4/4] 客户端合并...")
    client = LocalChunkClient(chunks_dir=output_dir, workers=4)
    config_path = os.path.join(output_dir, 'config.json')
    
    if client.download(config_path, restored_file):
        restored_hash = calculate_file_hash(restored_file)
        
        print("\n" + "="*70)
        print("  验证结果")
        print("="*70)
        print(f"  原始哈希: {original_hash}")
        print(f"  恢复哈希: {restored_hash}")
        
        if original_hash == restored_hash:
            print("\n  ✓✓✓ 完美！文件完全一致！ ✓✓✓")
        else:
            print("\n  ✗✗✗ 错误！哈希不匹配！ ✗✗✗")
    else:
        print("\n  ✗✗✗ 合并失败！ ✗✗✗")
    
    print("="*70)
    
    # 清理测试文件
    print("\n清理测试文件...")
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    if os.path.exists(test_file):
        os.remove(test_file)
    if os.path.exists(restored_file):
        os.remove(restored_file)
    
    print("\n演示完成！")


if __name__ == '__main__':
    main()
