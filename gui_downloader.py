#!/usr/bin/env python3
"""
抖音 / TikTok 批量下载器 — GUI 入口文件
本文件只包含核心下载逻辑（后台线程运行、配置读写、模块动态加载等），
不包含任何 tkinter / GUI 相关代码。
"""

import sys
import os

# 修复 PyInstaller 打包环境中子进程（如 Playwright 启动的浏览器）
# 因为 LD_LIBRARY_PATH 污染而崩溃的问题
if getattr(sys, 'frozen', False):
    for key in ['LD_LIBRARY_PATH', 'LIBPATH', 'DYLD_LIBRARY_PATH']:
        orig_key = key + '_ORIG'
        if orig_key in os.environ:
            os.environ[key] = os.environ[orig_key]
        else:
            os.environ.pop(key, None)

import json
import ssl
import importlib
import threading
import queue

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from playwright.sync_api import sync_playwright

# 禁用全局 SSL 证书验证，防止本地 CA 证书缺失导致网络请求失败
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# 强制设置浏览器路径为用户的全局缓存目录，防止打包后寻找 tmp 目录而崩溃
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = os.path.expanduser('~/.cache/ms-playwright')

# ============================================================================
# 国内镜像加速：Playwright 浏览器下载（绕过 GFW）
# 多个镜像源按顺序尝试，第一个可用的会被使用
#   1. 阿里云 OSS (playwright-zh 官方镜像)
#   2. npmmirror（淘宝 npm 镜像的二进制文件）
#   3. GitHub Proxy（ghproxy 等公共代理）
# 设置 PLAYWRIGHT_DOWNLOAD_HOST 会让 playwright 从镜像源下载浏览器（~100MB）
# ============================================================================
if 'PLAYWRIGHT_DOWNLOAD_HOST' not in os.environ:
    _mirror_candidates = [
        'https://playwright-zh.oss-cn-hangzhou.aliyuncs.com',
        'https://cdn.npmmirror.com/binaries/playwright',
        'https://ghproxy.com/https://playwright.azureedge.net',
    ]
    import urllib.request as _ur
    _selected_mirror = None
    for _mirror in _mirror_candidates:
        try:
            _req = _ur.Request(_mirror, method='HEAD')
            _resp = _ur.urlopen(_req, timeout=5)
            if 200 <= _resp.status < 500:
                _selected_mirror = _mirror
                break
        except Exception:
            continue
        if _selected_mirror:
            break
    if _selected_mirror is None:
        # 默认选第一个（阿里云）
        _selected_mirror = _mirror_candidates[0]
    os.environ['PLAYWRIGHT_DOWNLOAD_HOST'] = _selected_mirror

# 同时设置 npm registry 为淘宝镜像（用于 python -m playwright install 内部可能调用的 npm 流程）
if 'npm_config_registry' not in os.environ:
    os.environ['npm_config_registry'] = 'https://registry.npmmirror.com'


# ============================================================================
# 配置文件读写
# ============================================================================

def load_config() -> dict:
    """读取脚本/exe 所在目录的 config.json；失败或不存在时返回默认值。"""
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        config_path = os.path.join(exe_dir, "config.json")
        if not os.path.exists(config_path):
            return {"lang": "zh"}
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                return {"lang": "zh"}
            return cfg
    except Exception:
        return {"lang": "zh"}


def save_config(cfg: dict) -> None:
    """将 dict 写回 config.json，UTF-8 编码，indent=2。失败只打印警告。"""
    try:
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        config_path = os.path.join(exe_dir, "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] save_config failed: {e}")


def get_lang() -> str:
    """返回当前语言设置（'zh' 或 'en'）。"""
    return load_config().get("lang", "zh")


# ============================================================================
# 工具函数
# ============================================================================

def get_default_output_dir(platform: str) -> str:
    """返回 Windows 桌面的绝对路径 + 对应子目录。
    'douyin'  -> ...\\Desktop\\douyin_downloads
    'tiktok'  -> ...\\Desktop\\tiktok_downloads
    """
    if platform == "douyin":
        subdir_name = "douyin_downloads"
    elif platform == "tiktok":
        subdir_name = "tiktok_downloads"
    else:
        subdir_name = "downloads"

    candidates = [
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "桌面"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return os.path.join(c, subdir_name)
    # 若桌面都不可用，回退到用户主目录/downloads
    home_downloads = os.path.join(os.path.expanduser("~"), "downloads")
    if os.path.isdir(os.path.dirname(home_downloads)):
        return os.path.join(home_downloads, subdir_name)
    return os.path.join(candidates[0], subdir_name)


def _mkdir_with_fallback(path: str, log_queue=None, lang: str = "zh") -> str:
    """创建输出目录，带重试和回退机制。
    返回实际使用的路径（可能是传入值或回退值）。
    失败时抛异常（调用方负责捕获并写入日志）。
    """
    path = os.path.abspath(os.path.normpath(path))

    # 快速路径：目录已存在
    try:
        if os.path.isdir(path):
            return path
    except Exception:
        pass

    # 正常创建：带重试（应对 Windows 杀毒软件瞬态锁定）
    import time as _time
    last_err = None
    for attempt in range(3):
        try:
            os.makedirs(path, exist_ok=True)
            if os.path.isdir(path):
                return path
        except Exception as e:
            last_err = e
            if attempt < 2:
                _time.sleep(0.5 + attempt * 0.5)
            continue

    # 回退到临时目录（若主路径不可用）
    try:
        temp_root = os.environ.get("TMP") or os.environ.get("TEMP") or os.path.expanduser("~")
        basename = os.path.basename(path.rstrip(os.sep)) or "downloads"
        fallback = os.path.join(temp_root, basename)
        os.makedirs(fallback, exist_ok=True)
        if log_queue is not None:
            msg_tpl = "输出目录 {orig} 不可用，已回退到临时目录：{fallback}" if lang == "zh" \
                else "Output path {orig} inaccessible, falling back to: {fallback}"
            try:
                log_queue.put(("log", "warning", msg_tpl.format(orig=path, fallback=fallback)))
            except Exception:
                pass
        return fallback
    except Exception as e:
        if last_err is not None:
            raise last_err
        raise e


def get_module(platform: str):
    """动态加载对应平台模块。未知平台抛出 ValueError。"""
    if platform == "douyin":
        module_name = "douyin_image_downloader"
    elif platform == "tiktok":
        module_name = "tiktok_downloader"
    else:
        raise ValueError(f"Unknown platform: {platform}")
    return importlib.import_module(module_name)


def extract_unique_urls(platform_module, raw_text: str) -> list:
    """调用 platform_module.extract_urls_from_text(raw_text) 并去重（保持原顺序）。"""
    urls = platform_module.extract_urls_from_text(raw_text)
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


# ============================================================================
# 日志 / stdout 重定向：将 print 输出转为 log_queue 的 (log, level, text) 消息
# ============================================================================

class _GuiLogWriter:
    """把 stdout 写入到 log_queue，供主线程 GUI 消费。
    约定消息格式：
      ("log", "info" | "error" | "warning", text)
      ("progress", current, total)
      ("done", {"success": N, "fail": M, "cancelled": bool, "path": output_dir})
    """

    __slots__ = ("_queue", "_buffer")

    def __init__(self, log_queue):
        self._queue = log_queue
        self._buffer = []

    def write(self, text):
        if not text:
            return
        # 按行拆分，非空行入队（log / info 等级）
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                try:
                    self._queue.put(("log", "info", stripped))
                except Exception:
                    pass

    def flush(self):
        self._buffer = []


# ============================================================================
# 文案（中英双语，根据 get_lang() 选择）
# ============================================================================

_GUI_STRINGS = {
    "zh": {
        "no_links": "未检测到链接，请粘贴含有抖音或 TikTok 链接的文本后重试。",
        "found_links": "共解析到 {n} 个链接，开始下载...",
        "progress_text": "下载进度：{cur}/{total}（成功 {ok}，失败 {fail}）",
        "done_summary": "全部下载完成（成功 {ok} | 失败 {fail}）",
        "cancelled_summary": "下载已取消（成功 {ok} | 失败 {fail}）",
        "path_info": "存放目录：{path}",
        "error_prefix": "[错误] ",
    },
    "en": {
        "no_links": "No links detected. Please paste text containing Douyin or TikTok URLs and try again.",
        "found_links": "Parsed {n} URLs, starting download...",
        "progress_text": "Progress: {cur}/{total} (success {ok}, failed {fail})",
        "done_summary": "Download complete (Success: {ok} | Failed: {fail})",
        "cancelled_summary": "Download cancelled (Success: {ok} | Failed: {fail})",
        "path_info": "Saved to: {path}",
        "error_prefix": "[ERROR] ",
    },
}


def _current_lang() -> str:
    try:
        return get_lang()
    except Exception:
        return "zh"


# ============================================================================
# 后台线程执行的核心下载函数
# ============================================================================

def _send_log(log_queue, level: str, text: str):
    try:
        log_queue.put(("log", level, str(text)))
    except Exception:
        pass


def _send_done(log_queue, success: int, fail: int, cancelled: bool, path: str):
    try:
        log_queue.put(("done", {
            "success": int(success),
            "fail": int(fail),
            "cancelled": bool(cancelled),
            "path": str(path),
        }))
    except Exception:
        pass


def _send_progress(log_queue, current: int, total: int):
    try:
        log_queue.put(("progress", int(current), int(total)))
    except Exception:
        pass


def run_download(platform: str, raw_text: str, output_dir: str, log_queue, cancel_event=None):
    """在后台线程中执行下载。
    不使用任何 GUI / tkinter 调用，仅通过 log_queue 与主线程通信。
    """
    lang = _current_lang()
    original_stdout = sys.stdout
    success = 0
    fail = 0
    cancelled = False
    total = 0
    actual_output_dir = output_dir

    try:
        # 1. 创建输出目录（带重试和回退）
        try:
            actual_output_dir = _mkdir_with_fallback(output_dir, log_queue, lang)
        except Exception as e:
            err_msg = _GUI_STRINGS[lang].get("error_prefix", "") + str(e)
            _send_log(log_queue, "error", err_msg)
            hint = "提示：请尝试点击『浏览』选择其他目录（如 D:\\下载 或 文档）" \
                if lang == "zh" else "Hint: Click 'Browse' to choose another directory (e.g. Documents)"
            _send_log(log_queue, "warning", hint)
            _send_done(log_queue, 0, 0, False, output_dir)
            return

        # 2. 获取对应平台模块
        try:
            module = get_module(platform)
        except Exception as e:
            _send_log(log_queue, "error",
                      _GUI_STRINGS[lang].get("error_prefix", "") + str(e))
            _send_done(log_queue, 0, 0, False, actual_output_dir)
            return

        # 3. 重定向 stdout 到 GUI log writer，使被调用模块的 print 输出被捕获
        try:
            sys.stdout = _GuiLogWriter(log_queue)
        except Exception:
            pass

        # 4. 解析链接
        try:
            urls = extract_unique_urls(module, raw_text)
        except Exception as e:
            _send_log(log_queue, "error", f"链接解析失败: {e}")
            _send_done(log_queue, 0, 0, False, actual_output_dir)
            return
        total = len(urls)

        if total == 0:
            _send_log(log_queue, "info", _GUI_STRINGS[lang]["no_links"])
            hint2 = "提示：请粘贴含有 URL 或分享文本的内容（每行一个，或整段分享语）" \
                if lang == "zh" else "Hint: Paste content containing URLs (one per line or full share message)"
            _send_log(log_queue, "warning", hint2)
            _send_progress(log_queue, 0, 0)
            _send_done(log_queue, 0, 0, False, actual_output_dir)
            return

        _send_log(log_queue, "info", _GUI_STRINGS[lang]["found_links"].format(n=total))
        _send_log(log_queue, "info",
                  ("保存位置：" if lang == "zh" else "Saved to: ") + actual_output_dir)
        _send_progress(log_queue, 0, total)

        # 5. Playwright 启动 + 逐个链接下载
        # 启动前给个提示，因为浏览器下载可能比较慢
        _send_log(log_queue, "info",
                  ("正在初始化浏览器（首次运行会自动下载，约需 1-3 分钟，请耐心等待）..."
                   if lang == "zh"
                   else "Initializing browser (first run auto-downloads Chromium, may take 1-3 min)..."))

        browser = None
        try:
            with sync_playwright() as p:
                try:
                    module.ensure_browser_installed(p)
                except Exception as e:
                    _send_log(log_queue, "error",
                              f"{'浏览器安装失败' if lang == 'zh' else 'Browser install failed'}: {e}")
                    hint3 = "提示：请运行 'python -m playwright install chromium' 手动安装" \
                        if lang == "zh" else "Hint: Run 'python -m playwright install chromium' to install"
                    _send_log(log_queue, "warning", hint3)
                    _send_done(log_queue, 0, 0, False, actual_output_dir)
                    return

                try:
                    browser = p.chromium.launch(headless=True)
                except Exception as e:
                    _send_log(log_queue, "error",
                              f"{'浏览器启动失败' if lang == 'zh' else 'Browser launch failed'}: {e}")
                    _send_done(log_queue, 0, 0, False, actual_output_dir)
                    return

                _send_log(log_queue, "info",
                          ("浏览器就绪，开始下载..." if lang == "zh"
                           else "Browser ready, starting download..."))

                for i, url in enumerate(urls, 1):
                    # 取消检测
                    if cancel_event is not None and cancel_event.is_set():
                        cancelled = True
                        _send_log(log_queue, "warning",
                                  _GUI_STRINGS[lang]["cancelled_summary"].format(
                                      ok=success, fail=fail))
                        break

                    try:
                        result = module.process_single(url, browser, actual_output_dir, i, total)
                        if result:
                            success += 1
                        else:
                            fail += 1
                    except Exception as e:
                        fail += 1
                        _send_log(log_queue, "error",
                                  f"{'下载出错' if lang == 'zh' else 'Download error'} [{i}/{total}]: {e}")

                    _send_progress(log_queue, i, total)
        finally:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass

        # 6. 完成日志
        summary_key = "cancelled_summary" if cancelled else "done_summary"
        _send_log(log_queue, "info",
                  _GUI_STRINGS[lang][summary_key].format(ok=success, fail=fail))
        _send_log(log_queue, "info",
                  _GUI_STRINGS[lang]["path_info"].format(path=os.path.abspath(actual_output_dir)))

    except Exception as e:
        # 异常分支：发送错误日志
        try:
            sys.stdout = original_stdout
        except Exception:
            pass
        err_text = _GUI_STRINGS[lang].get("error_prefix", "") + str(e)
        _send_log(log_queue, "error", err_text)

    finally:
        # 无论是否异常，都必须恢复原 stdout
        try:
            sys.stdout = original_stdout
        except Exception:
            pass
        # 发送 done 消息（确保主线程恢复 UI 状态）
        _send_done(log_queue, success, fail, cancelled, actual_output_dir)


# ============================================================================
# 便于在后台线程中触发 run_download 的便捷入口
# ============================================================================

def start_download_thread(platform: str, raw_text: str, output_dir: str,
                          log_queue, cancel_event=None):
    """启动一个后台线程来运行 run_download，返回该线程对象。"""
    thread = threading.Thread(
        target=run_download,
        args=(platform, raw_text, output_dir, log_queue, cancel_event),
        daemon=True,
        name="DownloadWorker",
    )
    thread.start()
    return thread


# ============================================================================
# GUI 界面文案（中/英）
# ============================================================================

_GUI_DISCLAIMER_ZH = """================================================================================
                                【 免 责 声 明 】
================================================================================
 1. 【核心定位与技术本质】本工具仅作为网络自动化测试、前端渲染解析及编程学习的纯技术演示项目。
    本软件不提供、不存储、不分发任何媒体数据，仅为模拟用户在公开网络环境下的常规浏览器行为。
 2. 【禁止非法与商业用途】本软件及源代码严禁用于任何形式的商业盈利、代下载服务、批量刷量、恶意攻击
    或其他任何破坏网络生态及违反国家法律法规的行为。用户仅可用于个人私下的学习与合规技术验证。
 3. 【版权与知识产权免责】本软件运行中解析的数据均直接来源于目标平台公开页面。所有媒体资源知识产权
    归属于原作者或相关版权方。用户有义务在测试后24小时内销毁数据，严禁未经授权的传播或商用。
    作者对用户的任何侵权行为不承担连带赔偿责任。
 4. 【风控与账号安全免责】由于目标平台存在风控机制，频繁调用可能触发警报导致账号限流、IP被封禁。
    本软件不承诺规避上述风险，因使用本软件导致的任何账号财产损失或服务限制，由用户自行承担一切后果。
 5. 【绝对的免责与开发者权利】本软件按"原样"（AS IS）免费提供，不附带任何明示或暗示的担保。
    本软件作者及其合法授权团队不对因使用本软件造成的任何直接或间接损害承担责任，并在合法合规
    的前提下保留自主使用或研究本核心技术的权利。
 
 * 任何运行本软件的行为，即视为您已无条件接受本声明的所有条款并承诺自行承担100%独立法律责任。
================================================================================"""

_GUI_DISCLAIMER_EN = """================================================================================
                                【 DISCLAIMER 】
================================================================================
 1. [Core Purpose] This tool is purely a technical demonstration for web automation testing, frontend
    parsing, and programming learning. It simulates normal browser behavior in public networks.
 2. [Prohibited Uses] Commercial use, proxy downloading, malicious scraping, or any illegal activities
    are strictly prohibited. Users must only use this tool for personal learning and compliance testing.
 3. [Copyright Exemption] All parsed data originates from public pages. Intellectual property rights
    belong to the original creators. Users must destroy data within 24 hours. Unauthorized commercial
    use is forbidden. The author bears no liability for user infringement.
 4. [Risk & Account Safety] Frequent requests may trigger platform anti-bot mechanisms, leading to IP
    bans or account restrictions. The user assumes all consequences and liabilities.
 5. [Absolute Exemption & Dev Rights] Provided "AS IS" with no warranties. The author is not liable
    for any damages. The creator/author reserves the right to use this tool for legal research.
 
 * Running this software constitutes unconditional acceptance of this legally binding disclaimer.
================================================================================"""


_GUI_UI_STRINGS = {
    "zh": {
        "disclaimer_title": "免责声明",
        "agree_check": "我已阅读并同意以上免责声明",
        "dont_show": "不再提示",
        "continue_btn": "继续",
        "exit_btn": "退出",
        "must_agree": "请先勾选『我已阅读并同意以上免责声明』后再继续。",
        "app_title": "抖音 / TikTok 批量下载器",
        "platform_label": "平台：",
        "platform_douyin": "抖音 (Douyin)",
        "platform_tiktok": "TikTok",
        "links_label": "链接 / 分享文本：",
        "path_label": "保存路径：",
        "browse_btn": "浏览",
        "browse_title": "选择输出目录",
        "start_btn": "开始下载",
        "cancel_btn": "取消下载",
        "open_dir_btn": "打开输出目录",
        "status_ready": "就绪",
        "status_downloading": "下载中...",
        "status_cancelled": "已取消",
        "status_done": "完成（成功 {ok} | 失败 {fail}）",
        "empty_path": "输出目录为空，已使用默认路径：{path}",
        "path_not_found": "目录不存在，已创建：{path}",
        "no_output_path": "请先设置或开始下载以生成输出目录。",
        "open_dir_error": "无法打开目录：{err}",
        "cancel_log": "正在取消...",
    },
    "en": {
        "disclaimer_title": "Disclaimer",
        "agree_check": "I have read and agree to the above disclaimer",
        "dont_show": "Don't show again",
        "continue_btn": "Continue",
        "exit_btn": "Exit",
        "must_agree": "Please check 'I have read and agree to the above disclaimer' to continue.",
        "app_title": "Douyin / TikTok Batch Downloader",
        "platform_label": "Platform:",
        "platform_douyin": "Douyin",
        "platform_tiktok": "TikTok",
        "links_label": "Links / Share text:",
        "path_label": "Save to:",
        "browse_btn": "Browse",
        "browse_title": "Select output folder",
        "start_btn": "Start Download",
        "cancel_btn": "Cancel Download",
        "open_dir_btn": "Open Output Folder",
        "status_ready": "Ready",
        "status_downloading": "Downloading...",
        "status_cancelled": "Cancelled",
        "status_done": "Done (Success: {ok} | Failed: {fail})",
        "empty_path": "Output path is empty. Using default path: {path}",
        "path_not_found": "Directory does not exist, created: {path}",
        "no_output_path": "Please set an output path or start a download first.",
        "open_dir_error": "Failed to open folder: {err}",
        "cancel_log": "Cancelling...",
    },
}


def _t(key: str) -> str:
    """读取 GUI 文案（中/英）。"""
    lang = "zh"
    try:
        lang = get_lang()
    except Exception:
        lang = "zh"
    if lang not in _GUI_UI_STRINGS:
        lang = "zh"
    return _GUI_UI_STRINGS[lang].get(key, key)


# ============================================================================
# 免责声明对话框
# ============================================================================

class DisclaimerDialog(tk.Toplevel):
    """启动前显示的免责声明弹窗，模态。"""

    def __init__(self, master=None):
        super().__init__(master)
        self.title(_t("disclaimer_title"))
        self.resizable(False, False)
        # 居中
        self.update_idletasks()
        w, h = 640, 520
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

        self.agreed = False
        self.dont_show_again = False

        self._agree_var = tk.BooleanVar(value=False)
        self._dont_show_var = tk.BooleanVar(value=False)

        self._build_ui()

        # 模态
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_exit)

        # 居中于父窗口
        if master is not None:
            try:
                master.update_idletasks()
                mx = master.winfo_rootx()
                my = master.winfo_rooty()
                mw = master.winfo_width()
                mh = master.winfo_height()
                cx = mx + (mw - w) // 2
                cy = my + (mh - h) // 2
                self.geometry(f"{w}x{h}+{max(cx, 0)}+{max(cy, 0)}")
            except Exception:
                pass

        if master is not None:
            master.wait_window(self)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        lang = "zh"
        try:
            lang = get_lang()
        except Exception:
            lang = "zh"
        disclaimer_text = _GUI_DISCLAIMER_ZH if lang != "en" else _GUI_DISCLAIMER_EN

        text_frame = ttk.Frame(self)
        text_frame.pack(fill="both", expand=True, padx=12, pady=(12, 4))

        text_widget = scrolledtext.ScrolledText(
            text_frame, wrap="word", height=18, font=("Consolas", 10)
        )
        text_widget.pack(fill="both", expand=True)
        text_widget.insert("1.0", disclaimer_text)
        text_widget.configure(state="disabled")

        check_frame = ttk.Frame(self)
        check_frame.pack(fill="x", padx=12, pady=2)

        agree_chk = ttk.Checkbutton(
            check_frame,
            text=_t("agree_check"),
            variable=self._agree_var,
            command=self._on_agree_changed,
        )
        agree_chk.pack(anchor="w")

        dont_show_chk = ttk.Checkbutton(
            check_frame,
            text=_t("dont_show"),
            variable=self._dont_show_var,
        )
        dont_show_chk.pack(anchor="w")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=12, pady=12)

        self._continue_btn = ttk.Button(
            btn_frame, text=_t("continue_btn"), command=self._on_continue, state="disabled"
        )
        self._continue_btn.pack(side="right", padx=4)

        exit_btn = ttk.Button(btn_frame, text=_t("exit_btn"), command=self._on_exit)
        exit_btn.pack(side="right", padx=4)

    def _on_agree_changed(self):
        if self._agree_var.get():
            self._continue_btn.configure(state="normal")
        else:
            self._continue_btn.configure(state="disabled")

    def _on_continue(self):
        if not self._agree_var.get():
            try:
                messagebox.showwarning(self.title(), _t("must_agree"))
            except Exception:
                pass
            return
        self.agreed = True
        self.dont_show_again = bool(self._dont_show_var.get())

        # 保存到 config.json
        try:
            cfg = load_config()
            cfg["disclaimer_agreed"] = self.dont_show_again
            save_config(cfg)
        except Exception:
            pass

        self.destroy()

    def _on_exit(self):
        self.agreed = False
        try:
            root = self.master
            if root is not None:
                root.destroy()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


# ============================================================================
# 主应用窗口
# ============================================================================

class App(tk.Tk):
    """抖音 / TikTok 批量下载器主窗口。"""

    def __init__(self):
        super().__init__()
        self.title(_t("app_title"))
        self.minsize(900, 680)
        self.geometry("1000x720")
        
        # 注入现代化 Fluent Design 主题
        try:
            import sv_ttk
            sv_ttk.set_theme("dark")  # 启用暗黑模式
        except ImportError:
            pass

        # 核心状态
        self.cancel_event = threading.Event()
        self.download_thread = None
        self.log_queue = queue.Queue()
        self.is_downloading = False

        # 记录输出目录是否是用户自定义的
        self._output_dir_is_custom = False

        # 控件变量
        self._platform_var = tk.StringVar(value=_t("platform_douyin"))
        self._output_dir_var = tk.StringVar(value="")

        # 控件引用
        self._platform_combo = None
        self._links_text = None
        self._output_dir_entry = None
        self._action_btn = None
        self._open_dir_btn = None
        self._progress_bar = None
        self._progress_label = None
        self._log_text = None
        self._status_label = None

        self._build_ui()
        self._init_default_path()
        
        # 启动后静默检查更新
        try:
            import auto_updater
            # 延时 2 秒检查，避免阻塞主窗口渲染
            self.after(2000, lambda: auto_updater.check_for_updates(self, silent=True))
        except Exception:
            pass

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        pad = {"padx": 12, "pady": 4}

        # 平台选择行
        row1 = ttk.Frame(self)
        row1.pack(fill="x", **pad)
        ttk.Label(row1, text=_t("platform_label"), width=14).pack(side="left")
        self._platform_combo = ttk.Combobox(
            row1,
            textvariable=self._platform_var,
            values=[_t("platform_douyin"), _t("platform_tiktok")],
            state="readonly",
            width=20,
        )
        self._platform_combo.current(0)
        self._platform_combo.pack(side="left")
        self._platform_combo.bind("<<ComboboxSelected>>", self._on_platform_changed)

        # 链接输入行
        row2 = ttk.Frame(self)
        row2.pack(fill="both", expand=True, **pad)
        ttk.Label(row2, text=_t("links_label")).pack(anchor="w")
        self._links_text = tk.Text(row2, height=10, wrap="word")
        self._links_text.pack(fill="both", expand=True, pady=(4, 0))

        # 保存路径行
        row3 = ttk.Frame(self)
        row3.pack(fill="x", **pad)
        ttk.Label(row3, text=_t("path_label"), width=14).pack(side="left")
        self._output_dir_entry = ttk.Entry(row3, textvariable=self._output_dir_var, width=60)
        self._output_dir_entry.pack(side="left", fill="x", expand=True)
        browse_btn = ttk.Button(row3, text=_t("browse_btn"), command=self._on_browse)
        browse_btn.pack(side="left", padx=(8, 0))

        # 按钮行
        row4 = ttk.Frame(self)
        row4.pack(fill="x", **pad)
        self._action_btn = ttk.Button(row4, text=_t("start_btn"), command=self._on_action_clicked)
        self._action_btn.pack(side="left")
        self._open_dir_btn = ttk.Button(row4, text=_t("open_dir_btn"), command=self._on_open_dir)
        self._open_dir_btn.pack(side="left", padx=(8, 0))
        
        self._about_btn = ttk.Button(row4, text="关于 / 更新", command=self._show_about)
        self._about_btn.pack(side="right")
        
        def _toggle_lang():
            cfg = load_config()
            new_lang = "en" if cfg.get("lang", "zh") == "zh" else "zh"
            cfg["lang"] = new_lang
            save_config(cfg)
            if messagebox.askyesno("切换语言 / Language", "语言已更改，需要重启软件才能完全生效。是否立即重启？\nLanguage changed. Restart now?", parent=self):
                self.destroy()
                import os
                import sys
                os.execl(sys.executable, sys.executable, *sys.argv)
                
        self._lang_btn = ttk.Button(row4, text="🌐 Language / 语言", command=_toggle_lang)
        self._lang_btn.pack(side="right", padx=(0, 8))

        # 进度条行
        row5 = ttk.Frame(self)
        row5.pack(fill="x", **pad)
        self._progress_bar = ttk.Progressbar(row5, mode="determinate", maximum=100, value=0)
        self._progress_bar.pack(side="left", fill="x", expand=True)
        self._progress_label = ttk.Label(row5, text="0/0", width=10, anchor="e")
        self._progress_label.pack(side="left", padx=(8, 0))

        # 日志窗口
        row6 = ttk.Frame(self)
        row6.pack(fill="both", expand=True, **pad)
        self._log_text = scrolledtext.ScrolledText(row6, state="disabled", height=20, wrap="word")
        self._log_text.tag_configure("info")  # 默认前景
        self._log_text.tag_configure("warning", foreground="orange")
        self._log_text.tag_configure("error", foreground="red")
        self._log_text.pack(fill="both", expand=True)

        # ------------------- 注册右键菜单 -------------------
        self._context_menu = tk.Menu(self, tearoff=0)
        self._context_menu.add_command(label="剪切 / Cut", command=lambda: self.focus_get().event_generate("<<Cut>>"))
        self._context_menu.add_command(label="复制 / Copy", command=lambda: self.focus_get().event_generate("<<Copy>>"))
        self._context_menu.add_command(label="粘贴 / Paste", command=lambda: self.focus_get().event_generate("<<Paste>>"))
        self._context_menu.add_separator()
        self._context_menu.add_command(label="全选 / Select All", command=lambda: self.focus_get().event_generate("<<SelectAll>>"))

        def _show_context_menu(event):
            widget = event.widget
            if widget.winfo_class() in ("Entry", "TEntry", "Text", "ScrolledText"):
                widget.focus_set()
                self._context_menu.tk_popup(event.x_root, event.y_root)

        self.bind_class("Text", "<Button-3>", _show_context_menu)
        self.bind_class("Entry", "<Button-3>", _show_context_menu)
        self.bind_class("TEntry", "<Button-3>", _show_context_menu)
        self.bind_class("ScrolledText", "<Button-3>", _show_context_menu)

        # 状态栏
        self._status_label = ttk.Label(self, text=_t("status_ready"), anchor="w", relief="sunken")
        self._status_label.pack(fill="x", side="bottom")

    def _init_default_path(self):
        """根据上次保存或默认路径初始化输出目录。"""
        try:
            cfg = load_config()
            last = cfg.get("last_output_dir", "")
            if last:
                self._output_dir_var.set(last)
                self._output_dir_is_custom = True
                return
        except Exception:
            pass
        platform = self._current_platform()
        default_path = get_default_output_dir(platform)
        self._output_dir_var.set(default_path)
        self._output_dir_is_custom = False

    def _current_platform(self) -> str:
        value = self._platform_var.get()
        if value == _t("platform_tiktok"):
            return "tiktok"
        return "douyin"

    def _show_about(self):
        try:
            import auto_updater
            version = auto_updater.CURRENT_VERSION
        except ImportError:
            version = "v1.0.0"
            
        import webbrowser
        about_win = tk.Toplevel(self)
        about_win.title("关于")
        about_win.geometry("350x280")
        about_win.resizable(False, False)
        about_win.transient(self)
        about_win.grab_set()

        # 居中
        self.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 350) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 280) // 2
        about_win.geometry(f"+{max(0, x)}+{max(0, y)}")

        ttk.Label(about_win, text="MediaDownloader", font=("", 16, "bold")).pack(pady=(20, 5))
        ttk.Label(about_win, text=f"当前版本: {version}").pack(pady=2)
        ttk.Label(about_win, text="基于 Playwright 的无水印批量下载器").pack(pady=(10, 2))

        # 仓库链接
        repo_link = ttk.Label(about_win, text="🔗 项目主页: GitHub 仓库", foreground="#58a6ff", cursor="hand2")
        repo_link.pack(pady=4)
        repo_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Xynrin/tiktok-douyin-dl"))

        # 作者链接
        author_link = ttk.Label(about_win, text="👨‍💻 作者: Xynrin", foreground="#58a6ff", cursor="hand2")
        author_link.pack(pady=4)
        author_link.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Xynrin"))

        def _do_update():
            about_win.destroy()
            try:
                import auto_updater
                auto_updater.check_for_updates(self, silent=False)
            except ImportError:
                messagebox.showerror("错误", "自动更新模块未找到！", parent=self)

        ttk.Button(about_win, text="检查更新", command=_do_update).pack(pady=(20, 10))

    # ------------------------------------------------------------------ 事件处理


    def _on_platform_changed(self, _event=None):
        """切换平台时，若当前输出目录为默认的则跟着切换。"""
        try:
            platform = self._current_platform()
            default_path = get_default_output_dir(platform)
            current = self._output_dir_var.get().strip()
            # 判断当前目录是否为默认目录（douyin_downloads 或 tiktok_downloads）
            is_default = False
            try:
                if current == "":
                    is_default = True
                else:
                    norm_cur = os.path.normpath(current)
                    norm_default = os.path.normpath(default_path)
                    # 如果当前目录是任一默认形式，则视为默认
                    for p in (
                        get_default_output_dir("douyin"),
                        get_default_output_dir("tiktok"),
                    ):
                        if os.path.normpath(p) == norm_cur:
                            is_default = True
                            break
                    if not is_default and not self._output_dir_is_custom:
                        is_default = True
            except Exception:
                is_default = not self._output_dir_is_custom

            if is_default:
                self._output_dir_var.set(default_path)
                self._output_dir_is_custom = False
        except Exception:
            pass

    def _on_browse(self):
        try:
            current = self._output_dir_var.get().strip()
            platform = self._current_platform()
            initial = current if current else get_default_output_dir(platform)
            try:
                if not os.path.isdir(initial):
                    initial = os.path.expanduser("~")
            except Exception:
                initial = os.path.expanduser("~")

            chosen = filedialog.askdirectory(
                title=_t("browse_title"),
                initialdir=initial,
            )
            if chosen:
                self._output_dir_var.set(chosen)
                self._output_dir_is_custom = True
                try:
                    cfg = load_config()
                    cfg["last_output_dir"] = chosen
                    save_config(cfg)
                except Exception:
                    pass
        except Exception as e:
            try:
                messagebox.showerror(_t("app_title"), str(e))
            except Exception:
                pass

    def _on_open_dir(self):
        try:
            path = self._output_dir_var.get().strip()
            if not path:
                platform = self._current_platform()
                path = get_default_output_dir(platform)
                self._log_append("warning", _t("empty_path").format(path=path))
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                self._log_append("error", _t("open_dir_error").format(err=str(e)))
                return
            if not os.path.isdir(path):
                self._log_append("error", _t("open_dir_error").format(err="not a directory"))
                return
            try:
                if os.name == "nt":
                    os.startfile(path)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", path])
                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", path])
            except Exception as e:
                self._log_append("error", _t("open_dir_error").format(err=str(e)))
        except Exception as e:
            try:
                self._log_append("error", _t("open_dir_error").format(err=str(e)))
            except Exception:
                pass

    def _on_action_clicked(self):
        if self.is_downloading:
            # 取消下载
            try:
                self.cancel_event.set()
                self._log_append("warning", _t("cancel_log"))
                self._action_btn.configure(state="disabled")
            except Exception:
                pass
            return

        # 开始下载
        try:
            platform = self._current_platform()
            raw_text = self._links_text.get("1.0", "end-1c")
            output_dir = self._output_dir_var.get().strip()
            if not output_dir:
                output_dir = get_default_output_dir(platform)
                self._output_dir_var.set(output_dir)
                self._log_append("warning", _t("empty_path").format(path=output_dir))
            else:
                # 用户已修改目录，保存到配置
                try:
                    cfg = load_config()
                    cfg["last_output_dir"] = output_dir
                    save_config(cfg)
                except Exception:
                    pass

            self.cancel_event.clear()
            self._action_btn.configure(text=_t("cancel_btn"), state="normal")
            self._clear_log()
            self._progress_bar.configure(value=0, maximum=100)
            self._progress_label.configure(text="0/0")
            self._status_label.configure(text=_t("status_downloading"))
            self.is_downloading = True

            try:
                self.download_thread = start_download_thread(
                    platform, raw_text, output_dir, self.log_queue, self.cancel_event
                )
            except Exception as e:
                self._log_append("error", str(e))
                self.is_downloading = False
                self._action_btn.configure(text=_t("start_btn"), state="normal")
                self._status_label.configure(text=_t("status_ready"))
                return

            self.after(120, self._poll_queue)
        except Exception as e:
            try:
                messagebox.showerror(_t("app_title"), str(e))
            except Exception:
                pass
            self.is_downloading = False
            try:
                self._action_btn.configure(text=_t("start_btn"), state="normal")
            except Exception:
                pass

    # ------------------------------------------------------------------ 轮询 / 日志

    def _poll_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                self._handle_queue_item(item)
        except queue.Empty:
            pass
        except Exception:
            pass

        if self.is_downloading:
            try:
                self.after(120, self._poll_queue)
            except Exception:
                pass

    def _handle_queue_item(self, item):
        try:
            if not isinstance(item, (tuple, list)) or len(item) < 1:
                return
            msg_type = item[0]
            if msg_type == "log" and len(item) >= 3:
                level = item[1] if item[1] in ("info", "warning", "error") else "info"
                text = str(item[2])
                self._log_append(level, text)
            elif msg_type == "progress" and len(item) >= 3:
                current = int(item[1]) if isinstance(item[1], (int, float)) else 0
                total = int(item[2]) if isinstance(item[2], (int, float)) else 0
                try:
                    if total > 0:
                        self._progress_bar.configure(maximum=total, value=current)
                    else:
                        self._progress_bar.configure(value=0)
                except Exception:
                    pass
                try:
                    self._progress_label.configure(text=f"{current}/{total}")
                except Exception:
                    pass
            elif msg_type == "done":
                info = item[1] if len(item) > 1 and isinstance(item[1], dict) else {}
                success = int(info.get("success", 0) or 0)
                fail = int(info.get("fail", 0) or 0)
                cancelled = bool(info.get("cancelled", False))
                actual_path = info.get("path", "")
                self.is_downloading = False
                # 若实际使用的路径与界面不一致（回退到临时目录），同步更新 Entry
                try:
                    current = self._output_dir_var.get().strip()
                    if actual_path and os.path.normpath(actual_path) != os.path.normpath(current or ""):
                        self._output_dir_var.set(actual_path)
                        self._output_dir_is_custom = True
                        try:
                            cfg = load_config()
                            cfg["last_output_dir"] = actual_path
                            save_config(cfg)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    self._action_btn.configure(text=_t("start_btn"), state="normal")
                except Exception:
                    pass
                if cancelled:
                    status_text = _t("status_cancelled")
                else:
                    status_text = _t("status_done").format(ok=success, fail=fail)
                try:
                    self._status_label.configure(text=status_text)
                except Exception:
                    pass
                try:
                    self._log_append("info", status_text)
                except Exception:
                    pass
        except Exception:
            pass

    def _log_append(self, level: str, text: str):
        try:
            if not self._log_text:
                return
            self._log_text.configure(state="normal")
            self._log_text.insert("end", text + "\n", level)
            self._log_text.configure(state="disabled")
            self._log_text.see("end")
        except Exception:
            pass

    def _clear_log(self):
        try:
            if not self._log_text:
                return
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", "end")
            self._log_text.configure(state="disabled")
        except Exception:
            pass


# ============================================================================
# 启动入口
# ============================================================================

if __name__ == "__main__":
    try:
        app = App()
    except Exception as e:
        try:
            messagebox.showerror("Error", str(e))
        except Exception:
            print(f"[ERROR] Failed to start GUI: {e}")
        sys.exit(1)

    try:
        cfg = load_config()
        already_agreed = bool(cfg.get("disclaimer_agreed", False))
    except Exception:
        already_agreed = False

    if not already_agreed:
        try:
            dialog = DisclaimerDialog(app)
            if not dialog.agreed:
                try:
                    app.destroy()
                except Exception:
                    pass
                sys.exit(0)
        except SystemExit:
            raise
        except Exception as e:
            try:
                messagebox.showerror(_t("app_title"), str(e))
            except Exception:
                pass
            try:
                app.destroy()
            except Exception:
                pass
            sys.exit(1)

    try:
        app.mainloop()
    except Exception as e:
        try:
            messagebox.showerror(_t("app_title"), str(e))
        except Exception:
            print(f"[ERROR] {e}")

