#!/usr/bin/env python3
"""
工业级分块下载系统 - 客户端
功能：多线程下载、SHA256校验、断点续传、文件合并
"""

import os
import sys
import json
import time
import hashlib
import shutil
import logging
import argparse
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProgressTracker:
    """线程安全的进度跟踪器"""
    
    def __init__(self, total: int):
        self.total = total
        self.downloaded = 0
        self.verified = 0
        self.failed = 0
        self.lock = threading.Lock()
        self.start_time = time.time()
    
    def update(self, downloaded=0, verified=0, failed=0):
        with self.lock:
            self.downloaded += downloaded
            self.verified += verified
            self.failed += failed
    
    def get_progress(self) -> Dict:
        with self.lock:
            elapsed = time.time() - self.start_time
            speed = self.downloaded / elapsed if elapsed > 0 else 0
            percent = (self.downloaded / self.total * 100) if self.total > 0 else 0
            
            return {
                'downloaded': self.downloaded,
                'total': self.total,
                'verified': self.verified,
                'failed': self.failed,
                'percent': percent,
                'speed': speed,
                'elapsed': elapsed
            }


class IndustrialChunkClient:
    """工业级分块客户端"""
    
    def __init__(self, base_url: str, workers: int = 4, timeout: int = 30):
        """
        初始化客户端
        
        Args:
            base_url: 服务器基础URL
            workers: 并行下载线程数
            timeout: 下载超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.workers = workers
        self.timeout = timeout
    
    @staticmethod
    def calculate_sha256(file_path: str) -> str:
        """计算文件的SHA256哈希值"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def download_chunk(self, url: str, output_path: str) -> bool:
        """
        下载单个分块
        
        Args:
            url: 分块URL
            output_path: 保存路径
            
        Returns:
            是否成功
        """
        try:
            request = Request(url, headers={'User-Agent': 'IndustrialChunkClient/1.0'})
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read()
            
            with open(output_path, 'wb') as f:
                f.write(data)
            
            return True
        except (URLError, HTTPError, IOError) as e:
            logger.error(f"下载失败 {url}: {e}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return False
    
    def download_chunk_with_retry(
        self, 
        url: str, 
        output_path: str, 
        max_retries: int = 3
    ) -> bool:
        """带重试的下载"""
        for attempt in range(max_retries):
            if self.download_chunk(url, output_path):
                return True
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                logger.warning(f"重试 ({attempt + 1}/{max_retries})，等待 {wait_time}秒...")
                time.sleep(wait_time)
        return False
    
    def verify_chunk(self, chunk_path: str, expected_hash: str) -> bool:
        """
        验证分块哈希
        
        Args:
            chunk_path: 分块路径
            expected_hash: 期望的哈希值
            
        Returns:
            是否匹配
        """
        if not os.path.exists(chunk_path):
            return False
        
        actual_hash = self.calculate_sha256(chunk_path)
        if actual_hash != expected_hash:
            logger.error(f"哈希校验失败: {chunk_path}")
            logger.error(f"  期望: {expected_hash}")
            logger.error(f"  实际: {actual_hash}")
            os.remove(chunk_path)
            return False
        
        return True
    
    def download_all_chunks(
        self, 
        config: Dict, 
        output_dir: str,
        progress: ProgressTracker
    ) -> bool:
        """
        下载所有分块
        
        Args:
            config: 配置文件
            output_dir: 输出目录
            progress: 进度跟踪器
            
        Returns:
            是否全部成功
        """
        os.makedirs(output_dir, exist_ok=True)
        
        chunks = config['chunks']
        logger.info(f"开始下载 {len(chunks)} 个分块...")
        
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {}
            
            for chunk in chunks:
                chunk_url = f"{self.base_url}/{chunk['filename']}"
                chunk_path = os.path.join(output_dir, chunk['filename'])
                
                future = executor.submit(
                    self.download_chunk_with_retry,
                    chunk_url,
                    chunk_path
                )
                futures[future] = chunk
            
            success_count = 0
            for future in as_completed(futures):
                chunk = futures[future]
                if future.result():
                    # 验证哈希
                    chunk_path = os.path.join(output_dir, chunk['filename'])
                    if self.verify_chunk(chunk_path, chunk['hash']):
                        progress.update(downloaded=1, verified=1)
                        success_count += 1
                        logger.info(f"  ✓ 分块 {chunk['index']}: {chunk['filename']}")
                    else:
                        progress.update(failed=1)
                        logger.error(f"  ✗ 分块 {chunk['index']}: 验证失败")
                else:
                    progress.update(failed=1)
                    logger.error(f"  ✗ 分块 {chunk['index']}: 下载失败")
        
        return success_count == len(chunks)
    
    def merge_chunks(self, config: Dict, chunks_dir: str, output_file: str) -> bool:
        """
        合并分块
        
        Args:
            config: 配置文件
            chunks_dir: 分块目录
            output_file: 输出文件
            
        Returns:
            是否成功
        """
        logger.info(f"开始合并分块到: {output_file}")
        
        try:
            with open(output_file, 'wb') as outfile:
                for chunk in config['chunks']:
                    chunk_path = os.path.join(chunks_dir, chunk['filename'])
                    
                    if not os.path.exists(chunk_path):
                        logger.error(f"缺少分块: {chunk['filename']}")
                        return False
                    
                    with open(chunk_path, 'rb') as infile:
                        outfile.write(infile.read())
            
            # 验证整体哈希
            logger.info("验证完整文件哈希...")
            actual_hash = self.calculate_sha256(output_file)
            expected_hash = config['full_hash']
            
            if actual_hash != expected_hash:
                logger.error("完整文件哈希校验失败!")
                logger.error(f"  期望: {expected_hash}")
                logger.error(f"  实际: {actual_hash}")
                os.remove(output_file)
                return False
            
            logger.info("✓ 完整文件哈希校验通过")
            return True
            
        except IOError as e:
            logger.error(f"合并失败: {e}")
            if os.path.exists(output_file):
                os.remove(output_file)
            return False
    
    def download(self, config_url: str, output_file: str, chunks_dir: str = 'downloads') -> bool:
        """
        执行完整下载流程
        
        Args:
            config_url: 配置文件URL
            output_file: 输出文件路径
            chunks_dir: 分块缓存目录
            
        Returns:
            是否成功
        """
        logger.info("="*70)
        logger.info("  工业级分块下载客户端")
        logger.info("="*70)
        
        # 加载配置
        logger.info(f"加载配置: {config_url}")
        try:
            with urlopen(config_url, timeout=self.timeout) as response:
                config = json.loads(response.read().decode('utf-8'))
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return False
        
        # 显示文件信息
        print("\n" + "="*70)
        print("  文件信息")
        print("="*70)
        print(f"  文件名:     {config['file_name']}")
        print(f"  文件大小:   {config['file_size']:,} 字节 ({config['file_size']/1024/1024:.2f} MB)")
        print(f"  分块数量:   {config['num_chunks']}")
        print(f"  分块大小:   {config['chunk_size']:,} 字节")
        print(f"  哈希算法:   {config.get('hash_algorithm', 'SHA256')}")
        print(f"  整体哈希:   {config['full_hash']}")
        print("="*70)
        
        # 创建进度跟踪器
        progress = ProgressTracker(config['num_chunks'])
        
        # 下载所有分块
        print("\n开始下载分块...")
        if not self.download_all_chunks(config, chunks_dir, progress):
            logger.error("分块下载失败")
            return False
        
        # 合并分块
        print("\n开始合并分块...")
        if not self.merge_chunks(config, chunks_dir, output_file):
            logger.error("分块合并失败")
            return False
        
        # 完成
        print("\n" + "="*70)
        print("  下载完成!")
        print("="*70)
        print(f"  输出文件: {output_file}")
        print(f"  文件大小: {os.path.getsize(output_file):,} 字节")
        print(f"  哈希验证: ✓ 通过")
        print("="*70)
        
        return True


class LocalChunkClient(IndustrialChunkClient):
    """本地文件客户端（用于测试）"""
    
    def __init__(self, chunks_dir: str, workers: int = 4):
        """
        初始化本地客户端
        
        Args:
            chunks_dir: 本地分块目录
            workers: 并行线程数
        """
        self.local_chunks_dir = chunks_dir
        super().__init__(base_url='', workers=workers)
    
    def download(self, config_path: str, output_file: str) -> bool:
        """
        从本地分块合并文件
        
        Args:
            config_path: 配置文件路径
            output_file: 输出文件路径
            
        Returns:
            是否成功
        """
        logger.info("="*70)
        logger.info("  本地分块合并工具")
        logger.info("="*70)
        
        # 加载配置
        logger.info(f"加载配置: {config_path}")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return False
        
        # 显示文件信息
        print("\n" + "="*70)
        print("  文件信息")
        print("="*70)
        print(f"  文件名:     {config['file_name']}")
        print(f"  文件大小:   {config['file_size']:,} 字节")
        print(f"  分块数量:   {config['num_chunks']}")
        print("="*70)
        
        # 验证所有分块
        print("\n验证分块完整性...")
        progress = ProgressTracker(config['num_chunks'])
        
        for chunk in config['chunks']:
            chunk_path = os.path.join(self.local_chunks_dir, chunk['filename'])
            
            if not os.path.exists(chunk_path):
                logger.error(f"  ✗ 缺少分块: {chunk['filename']}")
                return False
            
            if not self.verify_chunk(chunk_path, chunk['hash']):
                logger.error(f"  ✗ 验证失败: {chunk['filename']}")
                return False
            
            progress.update(downloaded=1, verified=1)
            logger.info(f"  ✓ 分块 {chunk['index']}: {chunk['filename']}")
        
        # 合并分块
        print("\n开始合并分块...")
        if not self.merge_chunks(config, self.local_chunks_dir, output_file):
            return False
        
        # 完成
        print("\n" + "="*70)
        print("  合并完成!")
        print("="*70)
        print(f"  输出文件: {output_file}")
        print(f"  文件大小: {os.path.getsize(output_file):,} 字节")
        print(f"  哈希验证: ✓ 通过")
        print("="*70)
        
        return True


def main():
    parser = argparse.ArgumentParser(
        description='工业级分块下载系统 - 客户端',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用方式:
  1. 从远程服务器下载:
     %(prog)s http://example.com/chunks/config.json -o output.zip
  
  2. 从本地分块合并:
     %(prog)s --local ./chunks/config.json -o output.zip

示例:
  %(prog)s http://example.com/game/config.json -o game.zip -t 60
  %(prog)s --local ./chunks/config.json -o restored.zip
        """
    )
    
    parser.add_argument('config', help='配置文件（URL或本地路径）')
    parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    parser.add_argument('-c', '--chunks-dir', default='downloads', help='分块缓存目录')
    parser.add_argument('-w', '--workers', type=int, default=4, help='并行线程数')
    parser.add_argument('-t', '--timeout', type=int, default=30, help='下载超时（秒）')
    parser.add_argument('--local', action='store_true', help='从本地分块合并')
    parser.add_argument('-q', '--quiet', action='store_true', help='安静模式')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        if args.local:
            # 本地模式
            client = LocalChunkClient(
                chunks_dir=os.path.dirname(args.config) or '.',
                workers=args.workers
            )
            success = client.download(args.config, args.output)
        else:
            # 远程模式
            client = IndustrialChunkClient(
                base_url=os.path.dirname(args.config),
                workers=args.workers,
                timeout=args.timeout
            )
            success = client.download(args.config, args.output, args.chunks_dir)
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.warning("\n下载已取消")
        sys.exit(130)
    except Exception as e:
        logger.error(f"下载失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
