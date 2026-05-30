# 工业级分块下载系统

一个生产级别的 **大文件分块下载工具**，支持 SHA256 哈希校验、多线程并行处理、断点续传。

## 📋 目录

- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [使用方法](#-使用方法)
- [架构设计](#-架构设计)
- [API文档](#api文档)
- [配置文件格式](#配置文件格式)
- [常见问题](#常见问题)

## ✨ 功能特性

### 核心功能
- 🔪 **文件分块**：将大文件分割成指定大小的块
- 🔐 **哈希校验**：每个分块和完整文件都进行 SHA256 校验
- 🔄 **多线程**：服务端和客户端都支持多线程并行处理
- 📡 **远程下载**：支持从 HTTP 服务器下载分块
- 💾 **断点续传**：记录已下载分块，支持中断后继续
- 🔧 **本地合并**：支持从本地分块恢复文件

### 技术特性
- 🚀 **高性能**：使用 ThreadPoolExecutor 实现并行处理
- 📊 **进度跟踪**：实时显示下载/验证进度
- 🔁 **自动重试**：下载失败自动重试（指数退避）
- ⚙️ **可配置**：分块大小、线程数、超时时间均可配置
- 📝 **详细日志**：分级日志记录，便于调试

## 🚀 快速开始

### 1. 安装

```bash
# 克隆项目
git clone https://github.com/TC-STA/chunk-download-system.git
cd chunk-download-system

# 无需安装！Python 3.6+ 内置库即可运行
```

### 2. 服务端分块

```bash
# 基本用法 - 将文件分块
python3 server.py game.zip

# 指定分块大小
python3 server.py movie.mp4 --chunk-size 64MB

# 指定输出目录和线程数
python3 server.py large.iso -s 32MB -o dist -w 8
```

### 3. 客户端下载

```bash
# 从 HTTP 服务器下载
python3 client.py http://example.com/chunks/config.json -o game.zip

# 从本地分块合并
python3 client.py --local ./chunks/config.json -o restored.zip
```

### 4. 运行演示

```bash
# 运行完整演示
python3 test_demo.py
```

## 📖 使用方法

### 服务端命令

```bash
python3 server.py <文件路径> [选项]

位置参数:
  file                 要分块的文件路径

选项:
  -s, --chunk-size     分块大小 (默认: 32MB, 范围: 1MB-256MB)
  -o, --output         输出目录 (默认: chunks)
  -w, --workers        并行线程数 (默认: 4)
  -q, --quiet          安静模式
```

**示例**:
```bash
# 分块游戏安装包 (32MB 分块)
python3 server.py game_installer.exe

# 分块视频文件 (64MB 分块)
python3 server.py movie.mp4 -s 64MB

# 分块 ISO 镜像 (16MB 分块，8线程)
python3 server.py linux.iso -s 16MB -w 8 -o output
```

### 客户端命令

```bash
python3 client.py <配置> -o <输出文件> [选项]

位置参数:
  config               配置文件 (URL 或本地路径)

选项:
  -o, --output         输出文件路径 (必需)
  -c, --chunks-dir     分块缓存目录 (默认: downloads)
  -w, --workers        并行线程数 (默认: 4)
  -t, --timeout        下载超时秒数 (默认: 30)
  --local              从本地分块合并
  -q, --quiet          安静模式
```

**示例**:
```bash
# 从服务器下载
python3 client.py http://cdn.example.com/game/config.json -o game.exe -w 8

# 从本地分块恢复
python3 client.py --local ./chunks/config.json -o game.exe

# 自定义分块目录和超时
python3 client.py config.json -o output.zip -c my_cache -t 60
```

### 分块大小选择指南

| 文件大小 | 推荐分块大小 | 说明 |
|---------|------------|------|
| < 100MB | 8-16MB | 小文件，无需太大分块 |
| 100MB - 1GB | 16-32MB | 平衡选择 |
| 1GB - 10GB | 32-64MB | 大文件，减少分块数量 |
| > 10GB | 64-128MB | 超大文件，减少管理开销 |

## 🏗 架构设计

### 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     分块下载系统                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐              ┌──────────────┐       │
│  │   服务端      │              │   客户端      │       │
│  │              │              │              │       │
│  │  ┌────────┐ │   config    │  ┌────────┐  │       │
│  │  │ 读取文件 │─┼────────────┼─▶│ 下载配置 │  │       │
│  │  └────────┘ │   .json     │  └────────┘  │       │
│  │       │      │              │       │     │       │
│  │       ▼      │              │       ▼     │       │
│  │  ┌────────┐ │              │  ┌────────┐ │       │
│  │  │ 分块切割 │ │   chunks   │  │ 并行下载 │ │       │
│  │  └────────┘ ├────────────┼▶│ └────────┘ │       │
│  │       │      │              │       │     │       │
│  │       ▼      │              │       ▼     │       │
│  │  ┌────────┐ │              │  ┌────────┐ │       │
│  │  │ SHA256  │ │   verify   │  │ 哈希校验 │ │       │
│  │  │  校验  │ ├────────────┼─▶│ └────────┘ │       │
│  │  └────────┘ │              │       │     │       │
│  │              │              │       ▼     │       │
│  │              │              │  ┌────────┐ │       │
│  │              │              │  │ 文件合并 │ │       │
│  │              │              │  └────────┘ │       │
│  └──────────────┘              └──────────────┘       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 核心组件

#### IndustrialChunkServer
```python
class IndustrialChunkServer:
    def split_file(file_path, output_dir) -> Dict
    def calculate_sha256(file_path) -> str
```

#### IndustrialChunkClient
```python
class IndustrialChunkClient:
    def download(config_url, output_file, chunks_dir) -> bool
    def download_chunk(url, output_path) -> bool
    def verify_chunk(chunk_path, expected_hash) -> bool
    def merge_chunks(config, chunks_dir, output_file) -> bool
```

#### LocalChunkClient
```python
class LocalChunkClient:
    def download(config_path, output_file) -> bool
```

### 多线程设计

**服务端**:
```python
with ThreadPoolExecutor(max_workers=self.workers) as executor:
    for i in range(num_chunks):
        future = executor.submit(self._create_single_chunk, ...)
```

**客户端**:
```python
with ThreadPoolExecutor(max_workers=self.workers) as executor:
    for chunk in chunks:
        future = executor.submit(self.download_chunk_with_retry, ...)
```

## API文档

### 服务端 API

#### IndustrialChunkServer.__init__

```python
def __init__(self, chunk_size: int = None, workers: int = 4)
```

**参数**:
- `chunk_size`: 分块大小（字节），默认 32MB
- `workers`: 并行线程数，默认 4

**异常**:
- `ValueError`: 分块大小超出范围

#### IndustrialChunkServer.split_file

```python
def split_file(self, file_path: str, output_dir: str = 'chunks') -> Dict
```

**参数**:
- `file_path`: 要分块的文件路径
- `output_dir`: 输出目录

**返回**:
- 配置字典

**异常**:
- `FileNotFoundError`: 文件不存在

### 客户端 API

#### IndustrialChunkClient.__init__

```python
def __init__(self, base_url: str, workers: int = 4, timeout: int = 30)
```

**参数**:
- `base_url`: 服务器基础 URL
- `workers`: 并行下载线程数，默认 4
- `timeout`: 下载超时时间（秒），默认 30

#### IndustrialChunkClient.download

```python
def download(self, config_url: str, output_file: str, chunks_dir: str = 'downloads') -> bool
```

**参数**:
- `config_url`: 配置文件 URL
- `output_file`: 输出文件路径
- `chunks_dir`: 分块缓存目录

**返回**:
- 下载是否成功

## 配置文件格式

### config.json

```json
{
  "version": "1.0",
  "file_name": "game.zip",
  "file_size": 1073741824,
  "chunk_size": 33554432,
  "num_chunks": 32,
  "hash_algorithm": "SHA256",
  "full_hash": "a1b2c3d4e5f6...",
  "chunks": [
    {
      "index": 0,
      "start": 0,
      "end": 33554432,
      "size": 33554432,
      "filename": "game.zip.part00000",
      "hash": "51a75f4634dfa..."
    },
    {
      "index": 1,
      "start": 33554432,
      "end": 67108864,
      "size": 33554432,
      "filename": "game.zip.part00001",
      "hash": "084b42f6e95e..."
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| version | string | 配置版本号 |
| file_name | string | 原始文件名 |
| file_size | integer | 文件大小（字节） |
| chunk_size | integer | 分块大小（字节） |
| num_chunks | integer | 分块总数 |
| hash_algorithm | string | 哈希算法 |
| full_hash | string | 完整文件 SHA256 |
| chunks | array | 分块信息数组 |

## 常见问题

### Q: 分块丢失怎么办？

**A**: 如果某个分块损坏或丢失：
1. 从服务端重新下载该分块
2. 或重新运行服务端分块整个文件
3. 客户端会自动校验并报告损坏的分块

### Q: 如何选择分块大小？

**A**: 考虑因素：
- 网络稳定性：网络不稳定选小分块
- 文件大小：超大文件选大分块
- 并发数：线程多可以选小分块

**推荐**:
- 开发/测试：1-8MB
- 生产环境：16-64MB

### Q: 支持断点续传吗？

**A**: 客户端会：
1. 检查已下载的分块
2. 只下载缺失的分块
3. 验证每个分块的哈希
4. 中断后重新运行即可继续

### Q: 如何部署到生产环境？

**A**: 推荐架构：
```
                    ┌─────────────┐
                    │   用户端     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Web 服务器  │
                    │  (Nginx)    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐    │    ┌──────▼──────┐
       │  分块文件 1  │    │    │  分块文件 N  │
       └─────────────┘    │    └─────────────┘
                    ┌──────▼──────┐
                    │ config.json │
                    └─────────────┘
```

## 📄 许可证

MIT License - 可自由使用、修改和分发。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
