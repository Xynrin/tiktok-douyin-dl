#!/usr/bin/env python3
"""
TikTok Media Downloader (Linux Standalone)
Usage:
  python tiktok_downloader.py <Link/Sharing Text> [Output Directory]
"""

import sys
import os

# 修复 PyInstaller 打包环境中子进程（如 Playwright 启动的浏览器）因为 LD_LIBRARY_PATH 污染而崩溃的问题
if getattr(sys, 'frozen', False):
    for key in ['LD_LIBRARY_PATH', 'LIBPATH', 'DYLD_LIBRARY_PATH']:
        orig_key = key + '_ORIG'
        if orig_key in os.environ:
            os.environ[key] = os.environ[orig_key]
        else:
            os.environ.pop(key, None)

import re
import time
import urllib.request
import ssl
import json
from datetime import datetime
from playwright.sync_api import sync_playwright

# 禁用全局 SSL 证书验证，防止本地 CA 证书缺失导致网络请求失败
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# 尝试导入 Pillow
try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

# 版本控制与 GitHub 自动更新配置
VERSION = "1.1.6"
GITHUB_USER = "Xynrin"
GITHUB_REPO = "tiktok-douyin-dl"

# 强制设置浏览器路径为用户的全局缓存目录，防止打包后寻找 tmp 目录而崩溃
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.expanduser('~/.cache/ms-playwright')

# ============================================================================
# 国内镜像加速：Playwright 浏览器下载（绕过 GFW）
# 通过设置 PLAYWRIGHT_DOWNLOAD_HOST 让 playwright install 从国内镜像下载浏览器
# ============================================================================
if 'PLAYWRIGHT_DOWNLOAD_HOST' not in os.environ:
    _default_mirror_tt = 'https://playwright-zh.oss-cn-hangzhou.aliyuncs.com'
    try:
        import urllib.request as _ur_test_tt
        for _m_tt in [
            'https://playwright-zh.oss-cn-hangzhou.aliyuncs.com',
            'https://cdn.npmmirror.com/binaries/playwright',
            'https://ghproxy.com/https://playwright.azureedge.net',
        ]:
            try:
                _r_tt = _ur_test_tt.Request(_m_tt, method='HEAD')
                _resp_tt = _ur_test_tt.urlopen(_r_tt, timeout=4)
                if 200 <= _resp_tt.status < 500:
                    _default_mirror_tt = _m_tt
                    break
            except Exception:
                continue
    except Exception:
        pass
    os.environ['PLAYWRIGHT_DOWNLOAD_HOST'] = _default_mirror_tt

if 'npm_config_registry' not in os.environ:
    os.environ['npm_config_registry'] = 'https://registry.npmmirror.com'

# 读取本地语言设置
LANG = "zh"
try:
    exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    config_path = os.path.join(exe_dir, "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            LANG = cfg.get("lang", "zh")
except Exception:
    pass

# 翻译字典
STRINGS = {
    "zh": {
        "disclaimer_title": "================================================================================\n                                【 免 责 声 明 】\n================================================================================",
        "disclaimer_text": """ 1. 本工具（以下简称“本软件”）仅限用于个人学习研究、学术交流及网页技术备份
    测试，严禁用于任何商业用途、非法抓取或网络攻击。
 2. 本软件所下载的所有音视频、图文等媒体资源，其知识产权及著作权归原作者/
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
    停止使用并卸载本软件。""",
        "disclaimer_agree": "\n👉 是否已阅读、理解并完全同意接受上述免责声明의全部条款？(输入 y 继续 / 任意其他键退出): ",
        "disclaimer_declined": "👋 您拒绝了免责声明，程序已退出。",
        "title_banner": "┌────────────────────────────────────────┐\n│     TikTok图文/视频批量无水印下载器    │\n└────────────────────────────────────────┘",
        "update_found": "\n✨ 发现新版本: v{latest_version} (当前版本: v{VERSION})",
        "changelog_title": "\n📝 更新日志 / Changelog:",
        "update_confirm": "\n👉 是否立即自动下载并升级为最新版本？(y/n): ",
        "update_success": "🎉 升级成功！请重新运行程序即可启动最新版本。",
        "update_failed": "⚠️  检查更新失败 (网络超时或未公开): {err}",
        "update_hint": "💡 提示：运行 `tiktok-dl` 交互模式可一键完成自动升级。",
        "input_prompt": "\n👉 输入链接/分享文本 (输入 'q' 退出): ",
        "save_dir_prompt": "📂 保存目录 (回车默认: {default_dir}): ",
        "parsing": "🔍 正在解析，请稍候...",
        "no_links": "✗ 未检测到任何可解析的 TikTok 链接",
        "legal_warning": "\n⚠️  法律提示：运行本程序即代表您已默认同意《免责声明》中的所有条款。\n   所有知识产权、平台协议及法律相关风险均由使用者自行承担。\n",
        "download_done": "\n✨ 全部下载完成 (成功: {success} | 失败: {fail})",
        "save_dir_info": "📂 存放目录: {path}",
        "parse_failed": "✗ 解析或下载失败: {err}",
        "video_found": "🎬 视频 | {title} (ID: {id})",
        "image_found": "📸 图文 | {title} (ID: {id} | 共 {count} 张图片)",
        "download_success": "  └─ ✓ 下载成功: {filename} ({size} | {resolution})",
        "download_failed": "  └─ ✗ 下载失败: {err}",
        "browser_not_found": "🌐 未检测到内置浏览器 (Chromium)。正在为您自动下载并安装，请稍候...",
        "browser_install_failed": "❌ 自动安装浏览器失败 (错误码: {code})。您可以尝试手动运行 'playwright install chromium' 安装。",
        "browser_install_success": "✅ 浏览器安装成功！"
    },
    "en": {
        "disclaimer_title": "================================================================================\n                                【 DISCLAIMER 】\n================================================================================",
        "disclaimer_text": """ 1. This tool (hereinafter referred to as "the software") is strictly for personal 
    learning, research, academic exchanges, and technical backup tests. Commercial 
    use, malicious scraping, or network attacks are strictly prohibited.
 2. All media resources (videos, images, etc.) downloaded belong to the original 
    creators/copyright owners. Users must delete them within 24 hours and must not 
    redistribute, modify, upload, or use them for profit without authorization.
 3. Users must comply with local laws and platform Terms of Service. The user assumes 
    full responsibility for any legal disputes, copyright lawsuits, financial damages, 
    account restrictions, or IP bans caused by using this software.
 4. This software is provided "AS IS" without warranties of any kind. Under no 
    circumstances shall the author be liable for any direct, indirect, incidental, 
    or special damages arising from the use or inability to use this software.
 5. Running, distributing, or using this software constitutes unconditional acceptance 
    of this disclaimer. If you disagree with any terms, please stop using and uninstall 
    this software immediately.""",
        "disclaimer_agree": "\n👉 Have you read, understood and agreed to all the terms? (Type y to continue / any other key to exit): ",
        "disclaimer_declined": "👋 You declined the disclaimer. Program exited.",
        "title_banner": "┌────────────────────────────────────────┐\n│      TikTok Media Batch Downloader     │\n└────────────────────────────────────────┘",
        "update_found": "\n✨ New version found: v{latest_version} (Current version: v{VERSION})",
        "changelog_title": "\n📝 Changelog:",
        "update_confirm": "\n👉 Would you like to download and upgrade now? (y/n): ",
        "update_success": "🎉 Upgrade successful! Please re-run the program.",
        "update_failed": "⚠️  Update check failed (timeout or private repo): {err}",
        "update_hint": "💡 Tip: Run `tiktok-dl` in interactive mode to auto-upgrade.",
        "input_prompt": "\n👉 Enter TikTok link/sharing text (Type 'q' to exit): ",
        "save_dir_prompt": "📂 Save directory (Press Enter for default: {default_dir}): ",
        "parsing": "🔍 Parsing, please wait...",
        "no_links": "✗ No parseable TikTok links detected",
        "legal_warning": "\n⚠️  Legal Warning: Running this program means you agree to the Disclaimer.\n   All intellectual property and legal risks are assumed by the user.\n",
        "download_done": "\n✨ Download complete (Success: {success} | Fail: {fail})",
        "save_dir_info": "📂 Save directory: {path}",
        "parse_failed": "✗ Parsing or download failed: {err}",
        "video_found": "🎬 Video | {title} (ID: {id})",
        "image_found": "📸 Album | {title} (ID: {id} | {count} images)",
        "download_success": "  └─ ✓ Download success: {filename} ({size} | {resolution})",
        "download_failed": "  └─ ✗ Download failed: {err}",
        "browser_not_found": "🌐 Playwright browser (Chromium) not found. Downloading and installing now, please wait...",
        "browser_install_failed": "❌ Failed to install browser automatically (Exit code: {code}). Please run 'playwright install chromium' manually.",
        "browser_install_success": "✅ Browser installed successfully!"
    }
}

def t(key, **kwargs):
    text = STRINGS.get(LANG, STRINGS["zh"]).get(key, "")
    if kwargs:
        return text.format(**kwargs)
    return text

def parse_version(v_str):
    """解析版本字符串为数字元组，便于进行大小比较"""
    try:
        return tuple(int(x) for x in re.findall(r'\d+', v_str))
    except Exception:
        return (0,)

def check_for_updates(silent=False):
    """检查 GitHub 上的最新版本并提示自动更新"""
    if "YOUR_GITHUB_" in GITHUB_USER or "YOUR_GITHUB_" in GITHUB_REPO:
        return  # 若未配置 GitHub 仓库，则跳过检查

    latest_version = None
    changelog = ""
    download_url = ""
    tag_name = ""

    # 1. 首先尝试通过 GitHub API 获取最新版本
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
    api_success = False
    try:
        req = urllib.request.Request(
            api_url,
            headers={"User-Agent": "Mozilla/5.0 tiktok-dl-updater"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            tag_name = data.get("tag_name", "").strip()
            latest_version = tag_name.lstrip('v')
            changelog = data.get("body", "").strip()
            assets = data.get("assets", [])
            for asset in assets:
                if asset.get("name") == "tiktok-dl":
                    download_url = asset.get("browser_download_url")
                    break
            api_success = True
    except Exception:
        api_success = False

    # 2. 如果 API 请求失败，降级到网页重定向检查方法
    if not api_success:
        try:
            web_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(
                web_url,
                headers={"User-Agent": "Mozilla/5.0 tiktok-dl-updater"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                final_url = resp.geturl()
                if "/releases/tag/" in final_url:
                    tag_name = final_url.split("/releases/tag/")[-1].split("?")[0].split("#")[0].strip("/")
                    latest_version = tag_name.lstrip('v')
                    download_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/download/{tag_name}/tiktok-dl"
                    changelog = "⚠️  GitHub API rate limit exceeded, failed to fetch changelog." if LANG == "en" else "⚠️  GitHub API 速率受限，未能加载更新日志。请访问项目主页查看详情。"
        except Exception as e:
            if not silent:
                print(t("update_failed", err=e))
            return

    # 3. 统一进行版本对比与更新提示
    if latest_version and parse_version(latest_version) > parse_version(VERSION):
        print(t("update_found", latest_version=latest_version, VERSION=VERSION))
        
        if changelog:
            print(t("changelog_title"))
            print("─" * 50)
            print(changelog)
            print("─" * 50)
        
        if download_url:
            if not silent:
                confirm = input(t("update_confirm")).strip().lower()
                if confirm in ['y', 'yes']:
                    perform_self_update(download_url)
            else:
                print(t("update_hint", cmd="tiktok-dl"))

def perform_self_update(download_url):
    """下载最新版本的可执行文件并原地替换自身"""
    temp_exe = ""
    try:
        current_exe = os.path.abspath(sys.argv[0])
        temp_exe = current_exe + ".tmp"
        
        print("⚡ Downloading latest binary...")
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "Mozilla/5.0 tiktok-dl-updater"}
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            with open(temp_exe, "wb") as f:
                f.write(data)
        
        os.chmod(temp_exe, 0o755)
        os.replace(temp_exe, current_exe)
        print(t("update_success"))
        sys.exit(0)
    except Exception as e:
        print(f"❌ Update failed: {e}")
        if temp_exe and os.path.exists(temp_exe):
            try:
                os.remove(temp_exe)
            except Exception:
                pass

def extract_urls_from_text(text: str) -> list:
    """提取文本中的所有 TikTok 链接"""
    url_pattern = re.compile(r'https?://[a-zA-Z0-9][-a-zA-Z0-9\\._]*\btiktok\.com\b[-a-zA-Z0-9@:%_\+.~#?&//=]*')
    return url_pattern.findall(text)

def format_size(bytes_size):
    """人性化文件大小格式"""
    if not bytes_size:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"

def process_single(url, browser, output_base, index, total):
    """处理并下载单个 TikTok 链接"""
    print(f"\n[{index}/{total}] {t('parsing')}")
    
    # 用 Playwright 加载页面并等待 JSON
    page = None
    try:
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = context.new_page()

        # 引入反爬伪装，擦除 WebDriver 指纹
        try:
            from playwright_stealth import stealth_sync
            stealth_sync(page)
        except ImportError:
            pass
        # CDP 注入：隐藏 Playwright 自动化特征，防止被 TikTok 检测
        # 注意：新版 Playwright Python 需要用 context.new_cdp_session(page)
        try:
            cdp_session = context.new_cdp_session(page)
            cdp_session.send("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
                    window.chrome = { runtime: {} };
                    delete window.cdc_adoQpoasnfa4pcohlfhok;
                    delete window.$cdc_asdjflasutopfhvcZLmcfl_;
                """
            })
        except Exception:
            pass  # CDP 不可用时静默跳过
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(6000) # 等待完整渲染与状态注水
        
        rehyd_script = page.query_selector("script#__UNIVERSAL_DATA_FOR_REHYDRATION__")
        if not rehyd_script:
            # 备用：如果直接有 video src
            video_el = page.query_selector("video")
            if video_el:
                src = video_el.get_attribute("src")
                if src and not src.startswith("blob:"):
                    # 下载该非 blob 地址
                    filepath = os.path.join(output_base, f"tiktok_{int(time.time())}.mp4")
                    resp = page.request.get(src, headers={"Referer": "https://www.tiktok.com/"})
                    if resp.status == 200:
                        data = resp.body()
                        with open(filepath, "wb") as f:
                            f.write(data)
                    else:
                        raise Exception(f"HTTP {resp.status}")
                    print(t("download_success", filename=os.path.basename(filepath), size=format_size(len(data)), resolution="N/A"))
                    context.close()
                    return True
            raise Exception("No JSON script __UNIVERSAL_DATA_FOR_REHYDRATION__ or direct video src found.")
            
        json_content = rehyd_script.inner_text()
        data = json.loads(json_content)
        
        # 尝试提取 itemStruct 节点
        item = data.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail", {}).get("itemInfo", {}).get("itemStruct", {})
        if not item:
            # 备用路径寻找 (有时结构不同)
            for k, v in data.get("__DEFAULT_SCOPE__", {}).items():
                if isinstance(v, dict) and "itemInfo" in v:
                    item = v.get("itemInfo", {}).get("itemStruct", {})
                    break
        
        if not item:
            raise Exception("Failed to locate itemStruct in JSON data.")
            
        desc = item.get("desc", "tiktok_media").strip()
        # 清洗文件名安全字符
        desc_clean = re.sub(r'[\\/*?:"<>|]', "", desc)[:40] or "tiktok_media"
        aweme_id = item.get("id")
        if not aweme_id:
            aweme_id = str(int(time.time()))
            
        # 获取作者信息用于归档
        author_info = item.get("author", {})
        author_name = author_info.get("nickname") or author_info.get("uniqueId") or "Unknown_Author"
        author_clean = re.sub(r'[\\/*?:"<>|]', "", str(author_name)).strip()[:30]
        author_dir = os.path.join(output_base, author_clean)
        os.makedirs(author_dir, exist_ok=True)
            
        video_info = item.get("video", {})
        play_addr = video_info.get("playAddr")
        
        # 区分是视频还是图文
        images = item.get("imagePostInfo", {}).get("images", [])
        
        if images:
            # 图文相册下载
            title_log = t("image_found", title=desc_clean, id=aweme_id, count=len(images))
            print(title_log)
            
            output_dir = os.path.join(author_dir, f"[图文]_{aweme_id}_{desc_clean}")
            os.makedirs(output_dir, exist_ok=True)
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://www.tiktok.com/"
            }
            
            for i, img in enumerate(images, 1):
                img_url = None
                if "displayAddr" in img:
                    img_url = img["displayAddr"]
                elif "imageURL" in img and "urlList" in img["imageURL"]:
                    img_url = img["imageURL"]["urlList"][0]
                elif "thumbnail" in img and "urlList" in img["thumbnail"]:
                    img_url = img["thumbnail"]["urlList"][0]
                    
                if not img_url:
                    continue
                    
                img_filename = f"image_{i}.jpg"
                img_path = os.path.join(output_dir, img_filename)
                
                try:
                    resp = page.request.get(img_url, headers={"Referer": "https://www.tiktok.com/"})
                    if resp.status == 200:
                        img_data = resp.body()
                        with open(img_path, "wb") as f:
                            f.write(img_data)
                    else:
                        raise Exception(f"HTTP {resp.status}")
                    
                    # 使用 Pillow 分析尺寸
                    resolution = "N/A"
                    if PILImage:
                        try:
                            with PILImage.open(img_path) as p_img:
                                resolution = f"{p_img.width}x{p_img.height}"
                        except Exception:
                            pass
                    print(t("download_success", filename=img_filename, size=format_size(len(img_data)), resolution=resolution))
                except Exception as img_err:
                    print(t("download_failed", err=img_err))
                    
        elif play_addr:
            # 视频下载
            title_log = t("video_found", title=desc_clean, id=aweme_id)
            print(title_log)
            
            # 确定文件名和保存路径
            filename = f"[视频]_{aweme_id}_{desc_clean}.mp4"
            filepath = os.path.join(author_dir, filename)
            
            # 使用 Playwright page.request 下载直接的 playAddr（不需要水印提取，原始 CDN 无水印）
            resp = page.request.get(play_addr, headers={"Referer": "https://www.tiktok.com/"})
            if resp.status == 200:
                video_data = resp.body()
                with open(filepath, "wb") as f:
                    f.write(video_data)
            else:
                raise Exception(f"HTTP {resp.status}")
            
            resolution = video_info.get("definition", "N/A")
            print(t("download_success", filename=filename, size=format_size(len(video_data)), resolution=resolution))
        else:
            raise Exception("Neither playAddr nor images found in JSON state.")
            
        context.close()
        return True
    except Exception as e:
        print(t("parse_failed", err=e))
        if page:
            try:
                page.context.close()
            except Exception:
                pass
        return False

def _manual_install_chromium_tt(mirror: str = "https://playwright-zh.oss-cn-hangzhou.aliyuncs.com"):
    """备用策略：手动从镜像下载 Chromium 浏览器 zip 并解压到正确位置。"""
    import urllib.request
    import zipfile

    expected_exec_path = None
    browser_cache_dir = os.environ.get(
        'PLAYWRIGHT_BROWSERS_PATH',
        os.path.expanduser('~/.cache/ms-playwright')
    )
    try:
        from playwright.sync_api import sync_playwright as _sp3
        with _sp3() as pw:
            expected_exec_path = pw.chromium.executable_path
    except Exception:
        pass

    if not expected_exec_path:
        print("  ✗ 无法确定浏览器安装路径，请手动执行：")
        print("     set PLAYWRIGHT_DOWNLOAD_HOST=https://playwright-zh.oss-cn-hangzhou.aliyuncs.com")
        print("     python -m playwright install chromium")
        return False

    target_dir = os.path.dirname(os.path.dirname(expected_exec_path))
    revision = ''
    for part in expected_exec_path.split(os.sep):
        if part.startswith('chromium-'):
            revision = part.replace('chromium-', '')
            break

    zip_filename = 'chromium-win64.zip'
    target_exe = expected_exec_path

    if os.path.exists(target_exe):
        print("  ✓ 浏览器已安装，无需下载")
        return True

    mirrors = [
        mirror,
        'https://playwright-zh.oss-cn-hangzhou.aliyuncs.com',
        'https://cdn.npmmirror.com/binaries/playwright',
        'https://ghproxy.com/https://playwright.azureedge.net',
        'https://playwright.azureedge.net',
    ]

    print(f"  [备用策略] 期望的浏览器路径: {target_exe}")
    print(f"  [备用策略] 预计下载: {zip_filename}")
    print(f"  [备用策略] 请确保网络连接正常，大小约 100MB...")

    for idx, m in enumerate(mirrors, 1):
        url = f"{m.rstrip('/')}/builds/chromium/{revision}/{zip_filename}"
        print(f"  [{idx}/{len(mirrors)}] 尝试下载: {url[:70]}...")

        try:
            def _report_progress_tt(block_num, block_size, total_size):
                if total_size > 0:
                    percent = int(block_num * block_size * 100 / total_size)
                    if percent % 5 == 0:
                        mb_done = block_num * block_size / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        print(f"    下载中: {percent}% ({mb_done:.1f}/{mb_total:.1f} MB)", end='\r')

            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                }
            )
            zip_path, _ = urllib.request.urlretrieve(url=req, reporthook=_report_progress_tt)
            print(f"\n    ✓ 下载完成")

            print(f"    正在解压到: {target_dir}")
            os.makedirs(target_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(target_dir)

            try:
                os.remove(zip_path)
            except Exception:
                pass

            if os.path.exists(target_exe):
                print(f"    ✓ 浏览器已成功安装")
                return True
            else:
                print(f"    ✗ 解压完成但未找到 chrome.exe，尝试其他方式...")

        except Exception as ex:
            print(f"    ✗ 失败: {ex}")
            continue

    print(f"\n  ✗ 所有自动下载方式均失败，请手动执行：")
    print(f"    set PLAYWRIGHT_DOWNLOAD_HOST=https://playwright-zh.oss-cn-hangzhou.aliyuncs.com")
    print(f"    python -m playwright install chromium")
    print(f"    或手动下载: https://playwright-zh.oss-cn-hangzhou.aliyuncs.com/builds/chromium/{revision}/chromium-win64.zip")
    print(f"    解压到: {target_dir}")
    return False


def ensure_browser_installed(playwright_inst):
    """检查并自动安装缺失的 Playwright 浏览器（使用国内镜像源）"""
    if 'PLAYWRIGHT_DOWNLOAD_HOST' not in os.environ:
        os.environ['PLAYWRIGHT_DOWNLOAD_HOST'] = 'https://playwright-zh.oss-cn-hangzhou.aliyuncs.com'
    mirror = os.environ.get('PLAYWRIGHT_DOWNLOAD_HOST', '')
    try:
        browser = playwright_inst.chromium.launch(headless=True)
        browser.close()
    except Exception as e:
        err_msg = str(e)
        if "Executable doesn't exist" in err_msg or "looks like Playwright was just installed" in err_msg or "executable doesn't exist" in err_msg.lower():
            print(t("browser_not_found"))
            print(f"  [镜像] 使用下载源: {mirror}")
            print("  浏览器大小约 100MB，请耐心等待...")

            import sys as _sys_tt
            import subprocess
            from playwright._impl._driver import compute_driver_executable, get_driver_env
            
            driver_executable, driver_cli = compute_driver_executable()
            env = get_driver_env()

            try:
                creationflags = 0
                import os
                if os.name == 'nt':
                    creationflags = subprocess.CREATE_NO_WINDOW
                
                subprocess.run(
                    [driver_executable, driver_cli, "install", "chromium"],
                    env=env,
                    check=True,
                    creationflags=creationflags
                )
                print(t("browser_install_success"))
            except subprocess.CalledProcessError as exit_err:
                print(f"  [策略 1 失败] 错误码: {exit_err.returncode}，正在尝试备用方式下载...")
                _manual_install_chromium_tt(mirror)
            except Exception as inner_e:
                print(f"  [策略 1 失败] 错误: {inner_e}")
                _manual_install_chromium_tt(mirror)
        else:
            raise e

def download_urls(raw_input: str, output_dir: str):
    """批量下载 TikTok 链接"""
    urls = extract_urls_from_text(raw_input)
    if not urls:
        print(t("no_links"))
        return False

    # 数组去重
    unique_urls = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    urls = unique_urls

    total = len(urls)

    if not output_dir:
        output_dir = "tiktok_downloads"
    os.makedirs(output_dir, exist_ok=True)

    with sync_playwright() as p:
        ensure_browser_installed(p)
        browser = p.chromium.launch(headless=True)
        success = 0
        fail = 0
        for i, url in enumerate(urls, 1):
            if process_single(url, browser, output_dir, i, total):
                success += 1
            else:
                fail += 1
        browser.close()

    print(t("download_done", success=success, fail=fail))
    print(t("save_dir_info", path=os.path.abspath(output_dir)))
    return True

DISCLAIMER = """================================================================================
                                【 免 责 声 明 】
================================================================================
 1. 本工具（以下简称“本软件”）仅限用于个人学习研究、学术交流及网页技术备份
    测试，严禁用于任何商业用途、非法抓取或网络攻击。
 2. 本软件所下载的所有音视频、图文等媒体资源，其知识产权及著作权归原作者/
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

DISCLAIMER_EN = """================================================================================
                                【 DISCLAIMER 】
================================================================================
 1. This tool (hereinafter referred to as "the software") is strictly for personal 
    learning, research, academic exchanges, and technical backup tests. Commercial 
    use, malicious scraping, or network attacks are strictly prohibited.
 2. All media resources (videos, images, etc.) downloaded belong to the original 
    creators/copyright owners. Users must delete them within 24 hours and must not 
    redistribute, modify, upload, or use them for profit without authorization.
 3. Users must comply with local laws and platform Terms of Service. The user assumes 
    full responsibility for any legal disputes, copyright lawsuits, financial damages, 
    account restrictions, or IP bans caused by using this software.
 4. This software is provided "AS IS" without warranties of any kind. Under no 
    circumstances shall the author be liable for any direct, indirect, incidental, 
    or special damages arising from the use or inability to use this software.
 5. Running, distributing, or using this software constitutes unconditional acceptance 
    of this disclaimer. If you disagree with any terms, please stop using and uninstall 
    this software immediately.
================================================================================"""

def main():
    if len(sys.argv) >= 2:
        # Command line parameter mode
        if LANG == "zh":
            print("\n⚠️  法律提示：运行本程序即代表您已默认同意《免责声明》中的所有条款。")
            print("   所有知识产权、平台协议及法律相关风险均由使用者自行承担。\n")
        else:
            print("\n⚠️  Legal Warning: Running this program means you agree to the Disclaimer.")
            print("   All intellectual property and legal risks are assumed by the user.\n")
            
        check_for_updates(silent=True)
        raw_input = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "tiktok_downloads"
        download_urls(raw_input, output_dir)
    else:
        # Interactive mode
        if LANG == "zh":
            print(DISCLAIMER)
        else:
            print(DISCLAIMER_EN)
            
        try:
            agree = input(t("disclaimer_agree")).strip().lower()
            if agree not in ['y', 'yes']:
                print(t("disclaimer_declined"))
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Exited safely.")
            sys.exit(0)

        print(t("title_banner"))
        check_for_updates(silent=False)

        try:
            while True:
                raw_input = input(t("input_prompt")).strip()
                if not raw_input or raw_input.lower() in ['q', 'exit']:
                    print("👋 Exited safely." if LANG == "en" else "👋 已安全退出。")
                    break

                output_dir = input(t("save_dir_prompt", default_dir="tiktok_downloads")).strip()
                if not output_dir:
                    output_dir = "tiktok_downloads"

                print(t("parsing"))
                download_urls(raw_input, output_dir)
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Exited safely." if LANG == "en" else "\n👋 已安全退出。")

if __name__ == "__main__":
    main()
