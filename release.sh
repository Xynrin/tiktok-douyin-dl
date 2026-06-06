#!/bin/bash
# 遇到错误立即退出
set -e

# 1. 从 Python 脚本中自动读取当前版本号 (使用 douyin_image_downloader 的版本作为整体发布版本号)
VERSION=$(./.venv/bin/python -c "import douyin_image_downloader; print(douyin_image_downloader.VERSION)")
echo "📦 开始本地打包并发布版本: v$VERSION ..."

# 2. 运行 PyInstaller 编译两套独立软件
# 创建临时目录，复制 Playwright 驱动并排除浏览器文件以减小体积（从 370MB 减小到 ~50MB）
echo "📦 正在准备 Playwright 驱动 (排除浏览器以减小体积)..."
rm -rf playwright_driver_dist
cp -r .venv/lib/python3.14/site-packages/playwright/driver playwright_driver_dist
rm -rf playwright_driver_dist/package/.local-browsers

echo "🔨 正在编译 抖音下载器 (douyin-dl) ..."
rm -rf build
./.venv/bin/python -m PyInstaller --onefile --clean --name=douyin-dl \
  --add-data "playwright_driver_dist:playwright/driver" \
  douyin_image_downloader.py

echo "🔨 正在编译 TikTok 下载器 (tiktok-dl) ..."
rm -rf build
./.venv/bin/python -m PyInstaller --onefile --clean --name=tiktok-dl \
  --add-data "playwright_driver_dist:playwright/driver" \
  tiktok_downloader.py

# 清理临时目录
rm -rf playwright_driver_dist


# 3. 提交 .gitignore 等其他非源码文件的修改，并推送 Tag
git add .

# 检查是否有修改需要 commit（防止无修改时 commit 报错）
if ! git diff-index --quiet HEAD --; then
    git commit -m "release: v$VERSION"
fi

# 检查本地和远程是否已存在该 Tag，若存在则先删除（方便覆盖更新）
if git rev-parse "v$VERSION" >/dev/null 2>&1; then
    echo "⚠️ 检测到本地已存在 Tag v$VERSION，正在重置..."
    git tag -d "v$VERSION"
    git push origin --delete "v$VERSION" || true
fi

git tag "v$VERSION"
git push origin main
git push origin "v$VERSION"

# 4. 使用 gh CLI 一键创建 Release 并上传二进制文件
echo "🚀 正在创建 GitHub Release 并上传二进制文件..."

# 检查 gh 工具是否存在
if ! command -v gh &> /dev/null; then
    echo "❌ 错误: 未检测到 github-cli (gh)。请先运行 'sudo dnf install gh' 安装它。"
    exit 1
fi

# 检查 gh 是否已登录
if ! gh auth status &> /dev/null; then
    echo "🔑 请先在终端中运行 'gh auth login' 登录您的 GitHub 账号，然后重新运行本脚本。"
    exit 1
fi

# 创建或覆盖发布 Release (同时上传两套打包文件)
gh release create "v$VERSION" ./dist/douyin-dl ./dist/tiktok-dl --title "v$VERSION" --notes "Linux standalone builds for v$VERSION"

echo "🎉 发布成功！v$VERSION 二进制文件已上传至 GitHub Releases。"
