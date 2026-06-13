#!/usr/bin/env python3
"""
Playwright Chromium 浏览器安装脚本（国内镜像加速版）
Usage:
  python install_browser.py
  或双击运行 install_browser.bat（Windows）
"""
import sys
import os

# 修复 PyInstaller 打包环境的 LD_LIBRARY_PATH 问题
if getattr(sys, 'frozen', False):
    for key in ['LD_LIBRARY_PATH', 'LIBPATH', 'DYLD_LIBRARY_PATH']:
        orig_key = key + '_ORIG'
        if orig_key in os.environ:
            os.environ[key] = os.environ[orig_key]
        else:
            os.environ.pop(key, None)

# 设置浏览器缓存路径
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.expanduser('~/.cache/ms-playwright')

# 设置国内镜像
os.environ['PLAYWRIGHT_DOWNLOAD_HOST'] = 'https://playwright-zh.oss-cn-hangzhou.aliyuncs.com'
os.environ['npm_config_registry'] = 'https://registry.npmmirror.com'

# 禁用 SSL 验证（防止自签名证书问题）
import ssl
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

import urllib.request
import zipfile


def detect_chromium_version():
    """检测当前 Playwright 期望的 Chromium 路径和版本号"""
    print("=" * 60)
    print("  正在检测 Playwright 和期望的浏览器版本...")
    print("=" * 60)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exec_path = pw.chromium.executable_path
            print(f"\n  期望的浏览器路径: {exec_path}")

            # 解析版本号
            revision = ''
            for part in exec_path.split(os.sep):
                if part.startswith('chromium-'):
                    revision = part.replace('chromium-', '')
                    break

            cache_dir = os.path.dirname(os.path.dirname(exec_path))
            print(f"  浏览器缓存目录: {cache_dir}")
            print(f"  Chromium 版本号: {revision}")
            return exec_path, revision, cache_dir
    except Exception as e:
        print(f"\n  ✗ 检测失败: {e}")
        print("  请先确保已安装 playwright: pip install playwright")
        return None, None, None


def download_with_mirrors(revision: str, target_exe: str):
    """依次尝试多个镜像下载并解压 Chromium"""
    if os.path.exists(target_exe):
        print("\n  ✓ 浏览器已安装，无需下载")
        return True

    target_dir = os.path.dirname(os.path.dirname(target_exe))
    zip_filename = 'chromium-win64.zip'

    mirrors = [
        ('阿里云 OSS (playwright-zh)', 'https://playwright-zh.oss-cn-hangzhou.aliyuncs.com'),
        ('淘宝 npm 镜像', 'https://cdn.npmmirror.com/binaries/playwright'),
        ('GitHub 代理 (ghproxy)', 'https://ghproxy.com/https://playwright.azureedge.net'),
        ('官方 (Azure CDN, 可能被墙)', 'https://playwright.azureedge.net'),
    ]

    print(f"\n" + "=" * 60)
    print(f"  开始下载 Chromium (约 100MB)")
    print(f"  目标: {target_exe}")
    print("=" * 60)

    for idx, (name, url_base) in enumerate(mirrors, 1):
        url = f"{url_base.rstrip('/')}/builds/chromium/{revision}/{zip_filename}"
        print(f"\n  [{idx}/{len(mirrors)}] {name}")
        print(f"         URL: {url}")

        try:
            def progress(block_num, block_size, total_size):
                if total_size > 0:
                    percent = block_num * block_size * 100 // total_size
                    bar_len = 30
                    filled = bar_len * percent // 100
                    bar = '█' * filled + '░' * (bar_len - filled)
                    mb_done = block_num * block_size / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    print(f"  {bar} {percent:3d}% ({mb_done:5.1f}/{mb_total:.1f} MB)", end='\r')

            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                }
            )
            zip_path, headers = urllib.request.urlretrieve(url=req, reporthook=progress)
            print()  # newline after progress

            # 解压
            print(f"\n  正在解压到: {target_dir}")
            os.makedirs(target_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(target_dir)

            # 清理
            try:
                os.remove(zip_path)
            except Exception:
                pass

            # 验证
            if os.path.exists(target_exe):
                print(f"\n  ✓ 浏览器安装成功！")
                print(f"  ✓ 路径: {target_exe}")
                return True
            else:
                print(f"  ✗ 解压完成但未找到 chrome.exe，尝试下一个镜像...")

        except Exception as ex:
            print(f"\n  ✗ 失败: {ex}")
            continue

    return False


def verify_installation(target_exe: str):
    """验证浏览器是否可以正常启动"""
    print("\n" + "=" * 60)
    print("  正在验证浏览器安装...")
    print("=" * 60)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            version = browser.version
            browser.close()
            print(f"\n  ✓ 浏览器启动成功，版本: {version}")
            return True
    except Exception as e:
        print(f"\n  ✗ 浏览器启动失败: {e}")
        print("\n  提示: 尝试删除缓存目录后重新安装:")
        print(f"    rd /s /q {os.path.expanduser('~/.cache/ms-playwright')}")
        print(f"    然后重新运行: python install_browser.py")
        return False


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║        Playwright Chromium 浏览器安装工具                  ║
║        使用国内镜像，绕过 GFW 限制                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    # 步骤 1: 检测
    exec_path, revision, _ = detect_chromium_version()
    if not exec_path or not revision:
        print("\n  无法检测 Playwright，请先安装:")
        print("    pip install playwright")
        return False

    # 步骤 2: 检查是否已安装
    if os.path.exists(exec_path):
        print("\n  ✓ 浏览器已安装！")
        verify_installation(exec_path)
        return True

    # 步骤 3: 下载
    success = download_with_mirrors(revision, exec_path)

    if success:
        # 步骤 4: 验证
        verify_installation(exec_path)
        print(f"\n{'='*60}")
        print("  ✓ 安装完成！现在可以运行 GUI 了")
        print("    python gui_downloader.py")
        print(f"{'='*60}\n")
        return True
    else:
        print(f"\n{'='*60}")
        print("  ✗ 所有自动下载方式均失败，请尝试：")
        print(f"\n  方式 1 - 在命令行执行：")
        print(f"    set PLAYWRIGHT_DOWNLOAD_HOST=https://playwright-zh.oss-cn-hangzhou.aliyuncs.com")
        print(f"    python -m playwright install chromium")
        print(f"\n  方式 2 - 手动下载 zip：")
        print(f"    https://playwright-zh.oss-cn-hangzhou.aliyuncs.com/builds/chromium/{revision}/chromium-win64.zip")
        print(f"    解压到: {os.path.dirname(os.path.dirname(exec_path))}")
        print(f"\n  方式 3 - 使用国内 PyPI 镜像安装：")
        print(f"    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple playwright")
        print(f"    set PLAYWRIGHT_DOWNLOAD_HOST=https://playwright-zh.oss-cn-hangzhou.aliyuncs.com")
        print(f"    python -m playwright install chromium")
        print(f"{'='*60}\n")
        return False


if __name__ == "__main__":
    try:
        ok = main()
        sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        print("\n\n  用户中断")
        sys.exit(1)
