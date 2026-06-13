# 🚀 TikTok & Douyin Downloader (Windows GUI & Linux CLI)

[![Release](https://img.shields.io/github/v/release/Xynrin/tiktok-douyin-dl?color=brightgreen&logo=github&style=flat-square)](https://github.com/Xynrin/tiktok-douyin-dl/releases)
[![License](https://img.shields.io/github/license/Xynrin/tiktok-douyin-dl?color=blue&style=flat-square)](LICENSE)

A powerful cross-platform tool suite for downloading TikTok and Douyin videos/photos without watermarks. 
Available as a **Modern Windows GUI app** with one-click installation, and an **Independent Linux CLI tool**. **Zero environment dependencies** (built-in Python, Playwright, and drivers).

---

🌐 **[English]** | **[简体中文](README_zh.md)**

---

## ✨ v1.4+ New Features
* 🎨 **Modern UI Design**: Windows 11 Fluent Design (Dark Mode) with a minimalist interface and **seamless language switching (EN/ZH)**.
* 🌐 **NAS & Docker WebUI**: Deploy a web interface on NAS systems like FeiNiu OS (fnos) via Docker, enabling downloads from any device on the network without a client.
* 📁 **Smart Archive Management**: Automatically extracts the creator's username and groups downloaded videos and images into dedicated author folders.
* 🔄 **Silent Auto-Update**: Checks GitHub for updates on startup and performs seamless one-click background updates.
* 📦 **Standardized Installer**: Provides a standard Windows `Setup.exe` with desktop shortcuts and a robust uninstaller that leaves no trace.
* 🛡️ **Stealth Mode (Anti-Fingerprint)**: Uses advanced WebDriver evasion techniques to bypass platform bot detection and avoid IP bans.

## 📥 Download & Install

### 💻 Windows Users (GUI Recommended)
1. Go to the [Releases Page](https://github.com/Xynrin/tiktok-douyin-dl/releases/latest).
2. Download `MediaDownloader_Setup.exe` and install it.
3. *Language Switch:* Click the "🌐 Language / 语言" button in the app to switch languages and restart instantly.
4. *Optional:* Download the standalone `douyin-dl.exe` or `tiktok-dl.exe` if you prefer the CLI.

### 🐳 NAS Users (FeiNiu OS / Docker WebUI)
If you have a NAS device, create a Custom App (Docker Compose) and paste the following configuration:
```yaml
version: '3.8'
services:
  mediadownloader:
    build: https://github.com/Xynrin/tiktok-douyin-dl.git#main
    container_name: mediadownloader-webui
    restart: unless-stopped
    ports:
      - "7860:7860"
    volumes:
      - /vol1/downloads:/downloads   # Change the left side to your NAS download path
```
Deploy it and access `http://<NAS_IP>:7860` in your browser!

### 🐧 Linux Users (CLI)
Run the following command in your terminal to automatically install the latest Linux binaries to `~/.local/bin`:

```bash
curl -fsSL "https://raw.githubusercontent.com/Xynrin/tiktok-douyin-dl/main/install.sh?v=$(date +%s)" | bash
```

> **Note:** The install script looks for Linux binaries in the latest release. Make sure the Linux binaries (`douyin-dl` / `tiktok-dl`) are uploaded to the latest release.

---

## 🚀 Usage

### Windows GUI
Simply open **MediaDownloader** from your desktop, paste the share text/links, choose the platform (Douyin/TikTok), and click "Start Download".

### CLI Usage (Linux & Windows CMD)
```bash
douyin-dl "Share text or link" [output_directory]
tiktok-dl "Share text or link" [output_directory]
```

## ⚖️ Disclaimer
By downloading or using this software, you agree that it is strictly for educational, academic, and web-testing purposes. Commercial use or illegal scraping is strictly prohibited. You are solely responsible for any copyright or legal disputes arising from its use.
