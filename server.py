#!/usr/bin/env python3
"""
工业级分块下载系统 - 服务端
功能：文件分块、SHA256哈希校验、配置文件生成
"""

import os
import sys
import hashlib
import json
import argparse
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IndustrialChunkServer:
    """工业级分块服务端"""
    
    # 默认分块大小：32MB
    DEFAULT_CHUNK_SIZE = 32 * 1024 * 1024
    
    # 最小分块大小：1MB
    MIN_CHUNK_SIZE = 1 * 1024 * 1024
    
    # 最大分块大小：256MB
    MAX_CHUNK_SIZE = 256 * 1024 * 1024
    
    def __init__(self, chunk_size: Optional[int] = None, workers: int = 4):
        """
        初始化服务端
        
        Args:
            chunk_size: 分块大小（字节），默认32MB
            workers: 并行处理线程数
        """
        self.chunk_size = chunk_size or self.DEFAULT_CHUNK_SIZE
        self.workers = workers
        
        if not (self.MIN_CHUNK_SIZE <= self.chunk_size <= self.MAX_CHUNK_SIZE):
            raise ValueError(
                f"分块大小必须在 {self.MIN_CHUNK_SIZE/1024/1024:.0f}MB "
                f"到 {self.MAX_CHUNK_SIZE/1024/1024:.0f}MB 之间"
            )
    
    @staticmethod
    def calculate_sha256(file_path: str) -> str:
        """
        计算文件的SHA256哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            SHA256哈希值（64位十六进制字符串）
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _create_single_chunk(self, file_path: str, start: int, end: int, 
                           output_dir: str, chunk_index: int) -> Dict:
        """
        创建单个分块
        
        Args:
            file_path: 源文件路径
            start: 起始位置
            end: 结束位置
            output_dir: 输出目录
            chunk_index: 分块序号
            
        Returns:
            分块信息字典
        """
        chunk_size = end - start
        base_name = os.path.basename(file_path)
        chunk_filename = f"{base_name}.part{chunk_index:05d}"
        chunk_path = os.path.join(output_dir, chunk_filename)
        
        # 读取并保存分块
        with open(file_path, 'rb') as f:
            f.seek(start)
            data = f.read(chunk_size)
        
        with open(chunk_path, 'wb') as f:
            f.write(data)
        
        # 计算哈希
        chunk_hash = self.calculate_sha256(chunk_path)
        
        return {
            'index': chunk_index,
            'start': start,
            'end': end,
            'size': chunk_size,
            'filename': chunk_filename,
            'hash': chunk_hash
        }
    
    def split_file(self, file_path: str, output_dir: str = 'chunks') -> Dict:
        """
        将文件分块
        
        Args:
            file_path: 要分块的文件路径
            output_dir: 输出目录
            
        Returns:
            配置文件字典
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        file_size = os.path.getsize(file_path)
        base_name = os.path.basename(file_path)
        
        logger.info(f"开始分块: {base_name}")
        logger.info(f"文件大小: {file_size:,} 字节 ({file_size/1024/1024:.2f} MB)")
        logger.info(f"分块大小: {self.chunk_size:,} 字节 ({self.chunk_size/1024/1024:.2f} MB)")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 计算分块数量
        num_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        logger.info(f"分块数量: {num_chunks}")
        
        chunks = []
        
        # 使用多线程并行创建分块
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {}
            
            for i in range(num_chunks):
                start = i * self.chunk_size
                end = min(start + self.chunk_size, file_size)
                
                future = executor.submit(
                    self._create_single_chunk,
                    file_path, start, end, output_dir, i
                )
                futures[future] = i
            
            # 收集结果
            for future in as_completed(futures):
                chunk_info = future.result()
                chunks.append(chunk_info)
                logger.info(
                    f"  完成分块 {chunk_info['index']}: "
                    f"{chunk_info['filename']} "
                    f"({chunk_info['size']:,} 字节)"
                )
        
        # 按序号排序
        chunks.sort(key=lambda x: x['index'])
        
        # 计算整体哈希
        logger.info("计算整体文件哈希...")
        full_hash = self.calculate_sha256(file_path)
        
        # 生成配置
        config = {
            'version': '1.0',
            'file_name': base_name,
            'file_size': file_size,
            'chunk_size': self.chunk_size,
            'num_chunks': num_chunks,
            'chunks': chunks,
            'full_hash': full_hash,
            'hash_algorithm': 'SHA256'
        }
        
        # 保存配置
        config_path = os.path.join(output_dir, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"配置已保存: {config_path}")
        
        return config
    
    def print_summary(self, config: Dict):
        """打印分块摘要"""
        print("\n" + "="*70)
        print("  分块完成摘要")
        print("="*70)
        print(f"  文件名:     {config['file_name']}")
        print(f"  文件大小:   {config['file_size']:,} 字节")
        print(f"  分块大小:   {config['chunk_size']:,} 字节")
        print(f"  分块数量:   {config['num_chunks']}")
        print(f"  整体哈希:   {config['full_hash']}")
        print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='工业级分块下载系统 - 服务端',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s game.zip                      # 使用默认32MB分块
  %(prog)s movie.mp4 --chunk-size 16MB  # 使用16MB分块
  %(prog)s large.iso -s 64MB -o output # 使用64MB分块，输出到output目录

分块大小支持: MB, GB 单位，例如 16MB, 1GB
        """
    )
    
    parser.add_argument('file', help='要分块的文件路径')
    parser.add_argument(
        '-s', '--chunk-size',
        default='32MB',
        help='分块大小 (默认: 32MB, 范围: 1MB-256MB)'
    )
    parser.add_argument(
        '-o', '--output',
        default='chunks',
        help='输出目录 (默认: chunks)'
    )
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=4,
        help='并行线程数 (默认: 4)'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='安静模式，减少输出'
    )
    
    args = parser.parse_args()
    
    # 解析分块大小
    size_str = args.chunk_size.upper()
    if size_str.endswith('GB'):
        chunk_size = int(float(size_str[:-2]) * 1024 * 1024 * 1024)
    elif size_str.endswith('MB'):
        chunk_size = int(float(size_str[:-2]) * 1024 * 1024)
    elif size_str.endswith('KB'):
        chunk_size = int(float(size_str[:-2]) * 1024)
    else:
        chunk_size = int(size_str)
    
    # 设置日志级别
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        # 创建服务端并分块
        server = IndustrialChunkServer(
            chunk_size=chunk_size,
            workers=args.workers
        )
        config = server.split_file(args.file, args.output)
        server.print_summary(config)
        
        print(f"\n分块文件位置: {os.path.abspath(args.output)}")
        print(f"配置文件: {os.path.join(args.output, 'config.json')}")
        
    except Exception as e:
        logger.error(f"分块失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
