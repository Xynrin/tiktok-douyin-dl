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

    # 从 GitHub 获取最新 Release 的下载链接 (优先通过 302 重定向解析最新 tag，规避 GitHub API 频次限制)
    echo -e "🌐 正在获取 GitHub 最新发布版本信息..."
    
    # 通过 302 重定向 Location 头部获取最新发布版本 tag
    REDIRECT_URL=$(curl -sI "https://github.com/$GITHUB_USER/$GITHUB_REPO/releases/latest" | grep -i '^location:' | cut -d' ' -f2 | tr -d '\r\n' || true)
    
    if [ -n "$REDIRECT_URL" ] && [[ "$REDIRECT_URL" == *"/releases/tag/"* ]]; then
        TAG=$(basename "$REDIRECT_URL")
        DOWNLOAD_URL="https://github.com/$GITHUB_USER/$GITHUB_REPO/releases/download/$TAG/douyin-dl"
    else
        # 兜底方案：通过 REST API 解析 (若未发布任何 Release，重定向可能失败)
        echo -e "⚠️  未检测到重定向，尝试备用 API 接口解析..."
        API_URL="https://api.github.com/repos/$GITHUB_USER/$GITHUB_REPO/releases/latest"
        DOWNLOAD_URL=$(curl -s "$API_URL" | grep -o '"browser_download_url": *"[^"]*"' | grep -o 'http[^"]*' | grep -E '/douyin-dl$' | head -n 1 || true)
    fi
    
    if [ -z "$DOWNLOAD_URL" ] || [[ "$DOWNLOAD_URL" == *"rate limit exceeded"* ]]; then
        echo -e "${RED}❌ 错误: 未能在 GitHub 获取到名为 'douyin-dl' 的发布包地址。${NC}"
        echo -e "可能原因："
        echo -e "1. 您的 GitHub Actions 自动编译尚未结束（请稍候 2 分钟在 GitHub Actions 页面查看进度）"
        echo -e "2. 本机 IP 在 GitHub 上的 API 访问频次超限"
        exit 1
    fi

    echo -e "⚡ 正在从 GitHub 下载最新预编译包 (${BLUE}douyin-dl${NC}) ..."
    curl -L -# "$DOWNLOAD_URL" -o "$INSTALL_DIR/douyin-dl"
fi

# 2. 赋予执行权限
chmod +x "$INSTALL_DIR/douyin-dl"

# 3. 配置自定义终端命令
echo -e "\n${YELLOW}💬 配置自定义启动命令：${NC}"
read -p "请输入您希望使用的终端激活命令 (直接回车默认使用 'douyin-dl'): " CUSTOM_CMD < /dev/tty
if [ -z "$CUSTOM_CMD" ]; then
    CUSTOM_CMD="douyin-dl"
fi

WRAPPER_PATH="$BIN_DIR/$CUSTOM_CMD"

# 生成调用软链接或轻量包装
echo -e "📝 正在生成启动快捷方式 ${BLUE}$WRAPPER_PATH${NC} ..."
ln -sf "$INSTALL_DIR/douyin-dl" "$WRAPPER_PATH"

# 4. 自动配置环境变量 $PATH
NEED_SOURCE=false
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]] && [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\n⚙️  正在检测并配置环境变量..."
    
    # 写入 ~/.bashrc
    if [ -f "$HOME/.bashrc" ]; then
        if ! grep -q "export PATH=\"\$HOME/.local/bin:\$PATH\"" "$HOME/.bashrc"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
            echo -e "   ✓ 已向 ~/.bashrc 追加环境变量配置"
            NEED_SOURCE=true
        fi
    fi
    
    # 写入 ~/.zshrc
    if [ -f "$HOME/.zshrc" ]; then
        if ! grep -q "export PATH=\"\$HOME/.local/bin:\$PATH\"" "$HOME/.zshrc"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
            echo -e "   ✓ 已向 ~/.zshrc 追加环境变量配置"
            NEED_SOURCE=true
        fi
    fi
else
    echo -e "\n✅ 检测到 ~/.local/bin 已在您的环境变量中，无需额外配置。"
fi

echo -e "${GREEN}================================──────────────────${NC}"
echo -e "${GREEN}🎉 安装与配置成功！${NC}"
echo -e "${GREEN}================================──────────────────${NC}"
echo -e "📁 程序保存路径: ${BLUE}$INSTALL_DIR/douyin-dl${NC}"
echo -e "🚀 终端全局命令: ${BLUE}$CUSTOM_CMD${NC} (已链接到 $WRAPPER_PATH)"
echo -e ""
echo -e "${YELLOW}🔔 使用提示:${NC}"
if [ "$NEED_SOURCE" = true ]; then
    echo -e "1. 💡 ${YELLOW}请先运行 'source ~/.bashrc' (或 'source ~/.zshrc')，或重启终端使配置生效！${NC}"
    echo -e "2. 之后在终端任意目录下直接输入 ${GREEN}$CUSTOM_CMD${NC} 即可享受纯净下载！"
else
    echo -e "1. 终端任意目录下直接输入 ${GREEN}$CUSTOM_CMD${NC} 即可享受纯净下载！"
fi
echo -e "================================──────────────────"
