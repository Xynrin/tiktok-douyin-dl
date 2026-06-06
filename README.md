# 🚀 抖音图文 / 视频无水印下载器 (Linux 预编译版)

这是一个用 Python + Playwright 开发的命令行抖音图文与视频批量无水印下载工具。

已通过 PyInstaller 将所有 Python 运行沙箱环境、Pillow 图像分析库、Playwright 浏览器驱动，以及约 200MB 的内置 Chromium 浏览器完美打包成一个**完全独立、零环境依赖**的二进制文件。

---

## ✨ 核心特性
* 📦 **零依赖**：解压即用！无需目标系统安装 Python 3、Playwright 驱动或配置虚拟环境。
* 🌐 **极速安装**：支持通过一条终端指令直接从 GitHub Releases 自动安装/配置快捷命令。
* ⚡ **自动更新**：程序运行交互模式时，会自动查询 GitHub Releases，发现新版本可一键原地自动升级。
* 🎬 **智能检测**：自动提取抖音分享文本中的链接，支持单个/批量下载，支持图文及视频作品。
* 📊 **详细参数**：下载成功后自动解析并输出图片分辨率、文件大小、格式和保存位置等信息。
* ⚖️ **免责保障**：内置完备的法律与版权免责声明，保障开发者的合法权益。

---

## 🛠️ 安装方法 (Linux)

只需在终端中运行以下一键安装命令（它会自动拉取最新的预编译二进制文件，并将其软链接到您个人的 PATH 环境变量目录 `~/.local/bin` 中）：

```bash
curl -fsSL https://raw.githubusercontent.com/Xynrin/douyin-dl/main/install.sh | bash
```

> 💡 **请注意**：安装过程中您可以输入自定义的命令激活词（默认为 `douyin-dl`）。请确保您的环境变量包含 `~/.local/bin`，若没有，请在 `~/.bashrc` 或 `~/.zshrc` 末尾追加 `export PATH="$HOME/.local/bin:$PATH"` 并执行 `source` 生效。

---

## 🚀 使用方法

### 1. 交互式启动（推荐，支持一键升级）
直接在终端任意路径下运行您配置的激活命令（如默认的 `douyin-dl`）：
```bash
douyin-dl
```
* 首次运行将展示免责声明，输入 `y` 同意后即可进入交互提示。
* 输入抖音分享链接/作品ID，并根据提示设置存放目录（默认保存在 `douyin_downloads`）。
* 在有新版本发布时，进入交互界面将提示一键自动热更新。

### 2. 命令行单条静默运行（适合自动化脚本）
```bash
douyin-dl "分享文本或链接" [输出根目录]
```
示例：
```bash
douyin-dl "https://v.douyin.com/xxxxxx/" ./my_downloads
```

---

## ⚙️ 开发者二次编译 (本地打包)

如果您修改了代码并想在本地重新打包，只需在虚拟环境中运行：

```bash
# 1. 确保在本地虚拟环境安装了 pyinstaller
./.venv/bin/python -m pip install pyinstaller

# 2. 运行打包指令将 Chromium 编译进单文件中
./.venv/bin/pyinstaller --onefile --clean --name=douyin-dl \
  --add-data ".venv/lib/python3.14/site-packages/playwright/driver:playwright/driver" \
  douyin_image_downloader.py
```
编译完成的文件将保存在 `dist/douyin-dl` 目录下。

---

## ⚖️ 免责声明
本软件仅限用于个人技术研究、学术交流及网页技术备份测试，严禁用于任何商业用途、非法抓取或网络攻击。用户使用本软件时必须遵守当地法律法规。因使用本软件导致的一切著作权侵权纠纷与平台账号限制等风险均由使用者自行承担，本工具作者概不负责。
