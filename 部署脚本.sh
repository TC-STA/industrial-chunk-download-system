#!/bin/bash
# 部署脚本 - 自动化部署分块下载系统

set -e

echo "=========================================="
echo "  工业级分块下载系统 - 部署脚本"
echo "=========================================="

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查命令
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}错误: $1 未安装${NC}"
        exit 1
    fi
}

# 1. 检查依赖
echo -e "\n${YELLOW}[1/4] 检查依赖...${NC}"
check_command python3
check_command git
echo -e "${GREEN}✓ 依赖检查完成${NC}"

# 2. 克隆项目
echo -e "\n${YELLOW}[2/4] 克隆项目...${NC}"
if [ -d "industrial-chunk-download-system" ]; then
    echo "项目已存在，更新中..."
    cd industrial-chunk-download-system
    git pull
else
    git clone https://github.com/TC-STA/industrial-chunk-download-system.git
    cd industrial-chunk-download-system
fi
echo -e "${GREEN}✓ 项目准备完成${NC}"

# 3. 分块文件（可选）
echo -e "\n${YELLOW}[3/4] 分块文件（可选）${NC}"
read -p "请输入要分块的文件路径（留空跳过）: " FILE_PATH
if [ -n "$FILE_PATH" ]; then
    read -p "分块大小（默认 32MB）: " CHUNK_SIZE
    CHUNK_SIZE=${CHUNK_SIZE:-32MB}
    
    echo "开始分块..."
    python3 server.py "$FILE_PATH" --chunk-size "$CHUNK_SIZE"
    echo -e "${GREEN}✓ 分块完成${NC}"
fi

# 4. 启动服务
echo -e "\n${YELLOW}[4/4] 启动服务...${NC}"
if command -v docker &> /dev/null; then
    echo "检测到 Docker，是否使用 Docker 部署？ (y/n)"
    read -r USE_DOCKER
    if [ "$USE_DOCKER" = "y" ]; then
        echo "使用 Docker 部署..."
        docker-compose up -d
        echo -e "${GREEN}✓ Docker 服务已启动${NC}"
        echo -e "\n访问地址: http://localhost:8080"
    else
        echo "启动 Nginx..."
        sudo nginx -c "$(pwd)/nginx.conf"
        echo -e "${GREEN}✓ Nginx 已启动${NC}"
        echo -e "\n访问地址: http://localhost"
    fi
else
    echo "启动 Nginx..."
    sudo nginx -c "$(pwd)/nginx.conf"
    echo -e "${GREEN}✓ Nginx 已启动${NC}"
    echo -e "\n访问地址: http://localhost"
fi

echo -e "\n=========================================="
echo -e "${GREEN}  部署完成！${NC}"
echo "=========================================="
echo -e "\n使用方法:"
echo "  1. 将分块文件放在项目目录下"
echo "  2. 通过 Web 浏览器或客户端下载"
echo "  3. 使用 client.py 进行下载"
echo ""
echo "示例命令:"
echo "  python3 client.py http://localhost/config.json -o output.zip"
echo -e "\n==========================================\n"
