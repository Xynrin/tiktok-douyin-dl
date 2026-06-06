#!/bin/bash
# -----------------------------------------------------------------------------
# 抖音图文/视频无水印下载器 - Linux 一键安装与配置脚本 (支持 GitHub 极速下载)
# -----------------------------------------------------------------------------

set -e

# GitHub 仓库配置
GITHUB_USER="Xynrin"
GITHUB_REPO="douyin-dl"

INSTALL_DIR="$HOME/.local/share/douyin-downloader"
BIN_DIR="$HOME/.local/bin"

# 终端颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

echo -e "${BLUE}================================──────────────────${NC}"
echo -e "${BLUE}       🚀 抖音图文 / 视频下载器一键安装程序         ${NC}"
echo -e "${BLUE}================================──────────────────${NC}"

# 创建目录
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# 1. 确定安装文件来源
if [ -f "dist/douyin-dl" ]; then
    # 优先安装本地已编译的文件
    echo -e "📦 检测到本地已编译好的二进制文件，正在直接本地安装..."
    cp "dist/douyin-dl" "$INSTALL_DIR/"
else
    # 检查配置
    if [ "$GITHUB_USER" = "YOUR_GITHUB_USERNAME" ] || [ "$GITHUB_REPO" = "YOUR_GITHUB_REPO" ]; then
        echo -e "${RED}❌ 错误: 您尚未在 install.sh 中配置您的 GITHUB_USER / GITHUB_REPO。${NC}"
        echo -e "请在 GitHub 创建仓库后，修改本脚本中的配置，或在本地运行 pyinstaller 生成编译包。"
        exit 1
    fi

    # 从 GitHub 获取最新 Release 的下载链接
    echo -e "🌐 正在获取 GitHub 最新发布版本信息..."
    API_URL="https://api.github.com/repos/$GITHUB_USER/$GITHUB_REPO/releases/latest"
    
    # 尝试使用 curl 获取最新版本并提取二进制下载链接
    DOWNLOAD_URL=$(curl -s "$API_URL" | grep -o '"browser_download_url": *"[^"]*"' | grep -o 'http[^"]*' | grep -E '/douyin-dl$' | head -n 1 || true)
    
    if [ -z "$DOWNLOAD_URL" ]; then
        echo -e "${RED}❌ 错误: 未能在 GitHub Releases 资产中找到名为 'douyin-dl' 的发布包。${NC}"
        echo -e "请先在您的 GitHub 仓库发布一个 Release 并上传编译好的二进制文件。${NC}"
        exit 1
    fi

    echo -e "⚡ 正在从 GitHub 下载最新预编译包 (${BLUE}douyin-dl${NC}) ..."
    curl -L -# "$DOWNLOAD_URL" -o "$INSTALL_DIR/douyin-dl"
fi

# 2. 赋予执行权限
chmod +x "$INSTALL_DIR/douyin-dl"

# 3. 配置自定义终端命令
echo -e "\n${YELLOW}💬 配置自定义启动命令：${NC}"
read -p "请输入您希望使用的终端激活命令 (直接回车默认使用 'douyin-dl'): " CUSTOM_CMD
if [ -z "$CUSTOM_CMD" ]; then
    CUSTOM_CMD="douyin-dl"
fi

WRAPPER_PATH="$BIN_DIR/$CUSTOM_CMD"

# 生成调用软链接或轻量包装
echo -e "📝 正在生成启动快捷方式 ${BLUE}$WRAPPER_PATH${NC} ..."
ln -sf "$INSTALL_DIR/douyin-dl" "$WRAPPER_PATH"

echo -e "${GREEN}================================──────────────────${NC}"
echo -e "${GREEN}🎉 安装与配置成功！${NC}"
echo -e "${GREEN}================================──────────────────${NC}"
echo -e "📁 程序保存路径: ${BLUE}$INSTALL_DIR/douyin-dl${NC}"
echo -e "🚀 终端全局命令: ${BLUE}$CUSTOM_CMD${NC} (已链接到 $WRAPPER_PATH)"
echo -e ""
echo -e "${YELLOW}🔔 使用提示:${NC}"
echo -e "1. 请确保 ${BLUE}$BIN_DIR${NC} 已包含在您的环境变量 ${BLUE}\$PATH${NC} 中。"
echo -e "   若没有，请将下面这行代码加入到您的 ${BLUE}~/.bashrc${NC} 或 ${BLUE}~/.zshrc${NC} 文件末尾："
echo -e "   ${YELLOW}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
echo -e "2. 终端任意目录下直接运行 ${GREEN}$CUSTOM_CMD${NC} 即可享受纯净下载！"
echo -e "================================──────────────────"
