#!/usr/bin/env python3
"""
抖音图文/视频批量下载器
用法:
  python douyin_image_downloader.py <链接/分享文本> [输出目录]        # 单个作品
  python douyin_image_downloader.py <多条分享文本混合粘贴> [输出目录]  # 批量
示例:
  python douyin_image_downloader.py "5.84 复制打开抖音... https://v.douyin.com/xxx/ ..."
  python douyin_image_downloader.py https://v.douyin.com/xxx/
  python douyin_image_downloader.py 7634431189185036794 ./output

支持直接粘贴抖音APP的分享文本（可多条混合），自动提取链接。
支持图文和视频作品下载。
"""

import sys
import os
import re
import time
import urllib.request
import ssl
from datetime import datetime

# 禁用全局 SSL 证书验证，防止本地 CA 证书缺失导致网络请求失败
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# 尝试导入 Pillow 以读取图片尺寸
try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

# 版本控制与 GitHub 自动更新配置
VERSION = "1.1.1"
GITHUB_USER = "Xynrin"
GITHUB_REPO = "douyin-dl"

def check_for_updates(silent=False):
    """检查 GitHub 上的最新版本并提示自动更新"""
    if "YOUR_GITHUB_" in GITHUB_USER or "YOUR_GITHUB_" in GITHUB_REPO:
        return  # 若未配置 GitHub 仓库，则跳过检查
    
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "Mozilla/5.0 douyin-dl-updater"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            import json
            data = json.loads(resp.read().decode('utf-8'))
            latest_version = data.get("tag_name", "").strip().lstrip('v')
            
            # 简单的版本对比（如果不同则提示更新）
            if latest_version and latest_version != VERSION:
                print(f"\n✨ 发现新版本: v{latest_version} (当前版本: v{VERSION})")
                
                # 获取并展示更新日志 (Changelog)
                changelog = data.get("body", "").strip()
                if changelog:
                    print("\n📝 更新日志 / Changelog:")
                    print("─" * 50)
                    print(changelog)
                    print("─" * 50)

                assets = data.get("assets", [])
                download_url = ""
                for asset in assets:
                    if asset.get("name") == "douyin-dl":
                        download_url = asset.get("browser_download_url")
                        break
                
                if download_url:
                    if not silent:
                        confirm = input("\n👉 是否立即自动下载并升级为最新版本？(y/n): ").strip().lower()
                        if confirm in ['y', 'yes']:
                            perform_self_update(download_url)
                    else:
                        print("💡 提示：运行 `douyin-dl` 交互模式可一键完成自动升级。")
    except Exception as e:
        if not silent:
            print(f"⚠️  检查更新失败 (网络超时或仓库未公开): {e}")

def perform_self_update(download_url):
    """下载最新版本的可执行文件并原地替换自身"""
    temp_exe = ""
    try:
        # 获取当前运行的文件路径
        current_exe = os.path.abspath(sys.argv[0])
        temp_exe = current_exe + ".tmp"
        
        print("⚡ 正在从 GitHub 下载最新版本，请稍候...")
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "Mozilla/5.0 douyin-dl-updater"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            with open(temp_exe, "wb") as f:
                f.write(data)
        
        # 赋予执行权限并替换自身（Linux 支持直接替换运行中的文件）
        os.chmod(temp_exe, 0o755)
        os.replace(temp_exe, current_exe)
        print("🎉 升级成功！请重新运行程序即可启动最新版本。")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 自动升级失败: {e}")
        if temp_exe and os.path.exists(temp_exe):
            try:
                os.remove(temp_exe)
            except Exception:
                pass


# 强制 Playwright 将浏览器文件下载和查找到虚拟环境 (.venv) 中，不干扰系统其他部分
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ 需要安装 playwright 及其专属 chromium 浏览器:\n"
          "   .venv/bin/pip install playwright\n"
          "   PLAYWRIGHT_BROWSERS_PATH=0 .venv/bin/playwright install chromium")
    sys.exit(1)


def extract_urls_from_text(text: str) -> list:
    """从文本中提取所有抖音链接
    支持多条分享文本混合粘贴，自动过滤干扰字符。
    """
    # 提取所有 URL
    urls = re.findall(r'https?://[^\s]+', text)
    douyin_urls = []
    for u in urls:
        if 'douyin.com' in u:
            # 清理末尾可能的多余字符（分享文本中的干扰码）
            clean = u.rstrip('.,;:!?/ ')
            douyin_urls.append(clean)
    return douyin_urls


def extract_aweme_id(url_or_id: str) -> str:
    """从链接或直接ID中提取作品ID"""
    url_or_id = url_or_id.strip()
    if re.match(r'^\d{15,25}$', url_or_id):
        return url_or_id
    match = re.search(r'douyin\.com/(?:note|video)/(\d{15,25})', url_or_id)
    if match:
        return match.group(1)
    return url_or_id


def get_image_urls_from_dom(page) -> list:
    """从页面DOM中的img元素提取图片URL"""
    image_urls = []
    imgs = page.query_selector_all('img')
    seen_ids = set()
    for img in imgs:
        src = img.get_attribute('src') or ''
        if 'douyinpic.com' in src and 'tplv-dy-aweme-images' in src:
            file_id_match = re.search(r'tos-cn-i-[^/]+/([a-zA-Z0-9]+)~tplv-dy-aweme-images', src)
            if file_id_match:
                file_id = file_id_match.group(1)
                if file_id not in seen_ids:
                    seen_ids.add(file_id)
                    image_urls.append(src)
    return image_urls


def get_image_urls_from_page(page_content: str) -> list:
    """从页面源码中提取图文作品的图片URL"""
    pattern = r'(https://p\d+-pc-sign\.douyinpic\.com/tos-cn-i-[^/]+/[a-zA-Z0-9]+~tplv-dy-aweme-images[^"\'\\]+)'
    matches = re.findall(pattern, page_content)
    seen_ids = set()
    image_urls = []
    for url in matches:
        file_id_match = re.search(r'tos-cn-i-[^/]+/([a-zA-Z0-9]+)~tplv-dy-aweme-images', url)
        if file_id_match:
            file_id = file_id_match.group(1)
            if file_id not in seen_ids:
                seen_ids.add(file_id)
                clean_url = url.replace('\\u0026', '&')
                image_urls.append(clean_url)
    return image_urls


def get_video_id_from_iesdouyin(aweme_id: str) -> str:
    """通过 iesdouyin 分享页面获取 video_id"""
    share_url = f"https://www.iesdouyin.com/share/video/{aweme_id}/?region=CN&u_code=0&titleType=title"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    }
    try:
        req = urllib.request.Request(share_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            match = re.search(r'video_id[=:]["\']?([a-zA-Z0-9]+)', html)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"  ⚠ 获取 video_id 失败: {e}")
    return None


def download_video(aweme_id: str, filepath: str) -> tuple:
    """下载视频（无水印）
    返回: (是否成功, 使用的画质, 下载链接)
    """
    video_id = get_video_id_from_iesdouyin(aweme_id)
    if not video_id:
        return False, "", ""

    for ratio in ['1080p', '720p']:
        video_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={video_id}&ratio={ratio}&line=0"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        }
        try:
            req = urllib.request.Request(video_url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
                if len(data) < 10000:
                    continue
                with open(filepath, 'wb') as f:
                    f.write(data)
                return True, ratio, video_url
        except Exception as e:
            if ratio == '1080p':
                print(f"\n  ⚠ 1080p 画质获取失败，正在尝试 720p...")
            else:
                print(f"  ⚠ 720p 尝试失败: {e}")
    return False, "", ""


def process_single(url, browser, output_base, index, total):
    """处理单个作品（图文或视频）"""
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
    )
    page = context.new_page()

    prefix = f"[{index}/{total}] " if total > 1 else ""

    try:
        # 尝试静默打开页面并解析
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # 等待短链接跳转
        for _ in range(15):
            current_url = page.url
            if 'douyin.com/note/' in current_url or 'douyin.com/video/' in current_url:
                break
            time.sleep(1)

        # 等待内容渲染
        try:
            page.wait_for_selector('img[src*="douyinpic"]', timeout=10000)
        except Exception:
            pass
        time.sleep(2)

        current_url = page.url
        is_video = '/video/' in current_url

        # 提取作品ID
        id_match = re.search(r'douyin\.com/(?:note|video)/(\d{15,25})', current_url)
        aweme_id = id_match.group(1) if id_match else "unknown"

        # 获取标题，并防止过长导致排版混乱
        title = page.title().split(' - 抖音')[0] if page.title() else aweme_id
        if len(title) > 25:
            title = title[:22] + "..."

        type_tag = "🎬 视频" if is_video else "🖼 图文"
        print(f"\n{prefix}{type_tag} | {title} (ID: {aweme_id})")

        # 输出目录
        output_dir = output_base
        os.makedirs(output_dir, exist_ok=True)

        if is_video:
            # ===== 视频下载 =====
            context.close()

            now = datetime.now()
            ts = now.strftime("%Y%m%d_%H%M%S")
            filename = f"{aweme_id}_{ts}.mp4"
            filepath = os.path.join(output_dir, filename)
            
            success, ratio, video_url = download_video(aweme_id, filepath)
            if success:
                size_mb = os.path.getsize(filepath) / 1024 / 1024
                print(f"  └─ ✓ 下载成功: {filename} ({size_mb:.2f} MB | {ratio})")
                return True
            else:
                print(f"  └─ ✗ 视频下载失败")
                return False
        else:
            # ===== 图文下载 =====
            image_urls = get_image_urls_from_dom(page)
            if not image_urls:
                page_content = page.content()
                image_urls = get_image_urls_from_page(page_content)

            if not image_urls:
                print(f"  └─ ✗ 未找到可用的图片资源")
                context.close()
                return False

            print(f"  └─ 发现 {len(image_urls)} 张图片，开始下载：")

            cookies = context.cookies()
            cookies_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

            success_count = 0
            now = datetime.now()
            for i, img_url in enumerate(image_urls):
                ts = now.strftime("%Y%m%d_%H%M%S")
                ext = ".webp" if "webp" in img_url else ".jpeg"
                filename = f"{aweme_id}_{i+1:02d}_{ts}{ext}"
                filepath = os.path.join(output_dir, filename)

                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.douyin.com/",
                    "Cookie": cookies_str,
                    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                }
                try:
                    req = urllib.request.Request(img_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        data = resp.read()
                        if len(data) < 1000:
                            print(f"     ✗ 图片 {i+1} 数据为空，跳过")
                            continue
                        with open(filepath, 'wb') as f:
                            f.write(data)
                        
                        size_kb = os.path.getsize(filepath) / 1024
                        
                        # 解析图片尺寸和格式
                        img_details = ""
                        if PILImage:
                            try:
                                with PILImage.open(filepath) as img:
                                    img_details = f" | {img.size[0]}x{img.size[1]}"
                            except Exception:
                                pass
                        
                        print(f"     ✓ [{i+1}/{len(image_urls)}] {filename} ({size_kb:.1f} KB{img_details})")
                        success_count += 1
                except Exception as e:
                    print(f"     ✗ [{i+1}/{len(image_urls)}] 下载异常: {e}")

            context.close()
            return success_count > 0

    except Exception as e:
        print(f"\n{prefix}✗ 解析或下载失败: {e}")
        try:
            context.close()
        except:
            pass
        return False


def download_urls(raw_input: str, output_dir: str):
    """提取并下载给定的抖音链接/分享文本"""
    # 提取所有抖音链接
    urls = extract_urls_from_text(raw_input)

    if not urls:
        # 可能是纯作品ID
        if re.match(r'^\d{15,25}$', raw_input.strip()):
            urls = [f"https://www.douyin.com/note/{raw_input.strip()}"]
        else:
            print("✗ 未检测到任何可解析的抖音链接")
            return False

    # 去重
    seen = set()
    unique_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    urls = unique_urls

    total = len(urls)

    if not output_dir:
        output_dir = "douyin_downloads"
    os.makedirs(output_dir, exist_ok=True)

    # 启动浏览器（复用，批量下载更高效）
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        success = 0
        fail = 0
        for i, url in enumerate(urls, 1):
            if process_single(url, browser, output_dir, i, total):
                success += 1
            else:
                fail += 1

        browser.close()

    print(f"\n✨ 全部下载完成 (成功: {success} | 失败: {fail})")
    print(f"📂 存放目录: {os.path.abspath(output_dir)}")
    return True


DISCLAIMER = """================================================================================
                                【 免 责 声 明 】
================================================================================
 1. 本工具（以下简称“本软件”）仅限用于个人学习研究、学术交流及网页技术备份
    测试，严禁用于任何商业用途、非法抓取或网络攻击。
 2. 本软件所下载的所有音视频、图文等媒体资源，其知识产权及著作权均归原作者/
    版权所有者或相关平台所有。用户下载后应于24小时内删除，且不得在未经原作者
    授权的情况下进行二次传播、修改、上传或用于任何盈利性活动。
 3. 用户在使用本软件时，必须遵守当地法律法规、目的平台用户协议及相关服务条款。
    因使用本软件导致的一切直接或间接法律纠纷、版权诉讼、经济赔偿，或因频繁请求
    导致的平台账号限制、IP风控封禁等后果，均由使用者自行承担全部责任。
 4. 本软件按“原样”（AS IS）提供，不附带任何明示或暗示的保证，包括但不限于
    对特定用途的适用性。作者在任何情况下均不对因使用或无法使用本软件而产生的
    任何直接、间接、偶然、特殊或惩罚性损害（包括法律处罚）承担任何赔偿责任。
 5. 任何复制、运行、分发或以任何方式使用本软件的行为，即视为您已完全阅读、
    理解并无条件接受本声明的所有条款。如果您不同意本声明的任何内容，请立即
    停止使用并卸载本软件。
================================================================================"""


def main():
    if len(sys.argv) >= 2:
        # 带参数直接下载，打印免责提示但不阻塞脚本管道
        print("\n⚠️  法律提示：运行本程序即代表您已默认同意《免责声明》中的所有条款。")
        print("   所有知识产权、平台协议及法律相关风险均由使用者自行承担。\n")
        check_for_updates(silent=True)
        raw_input = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "douyin_downloads"
        download_urls(raw_input, output_dir)
    else:
        # 无参数进入交互模式，显示并强行拦截同意
        print(DISCLAIMER)
        try:
            agree = input("\n👉 是否已阅读、理解并完全同意接受上述免责声明的全部条款？(输入 y 继续 / 任意其他键退出): ").strip().lower()
            if agree not in ['y', 'yes']:
                print("👋 您拒绝了免责声明，程序已退出。")
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            print("\n👋 程序已安全退出。")
            sys.exit(0)

        print("\n┌────────────────────────────────────────┐")
        print("│      抖音图文/视频批量无水印下载器     │")
        print("└────────────────────────────────────────┘")

        check_for_updates(silent=False)

        # 无参数进入交互模式
        try:
            while True:
                raw_input = input("\n👉 输入链接/分享文本 (输入 'q' 退出): ").strip()
                if not raw_input or raw_input.lower() in ['q', 'exit']:
                    print("👋 已安全退出。")
                    break

                output_dir = input("📂 保存目录 (回车默认: douyin_downloads): ").strip()
                if not output_dir:
                    output_dir = "douyin_downloads"

                print("🔍 正在解析，请稍候...")
                download_urls(raw_input, output_dir)
        except (KeyboardInterrupt, EOFError):
            print("\n👋 已安全退出。")


if __name__ == "__main__":
    main()
