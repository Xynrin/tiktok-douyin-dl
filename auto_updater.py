import os
import sys
import threading
import urllib.request
import urllib.error
import json
import tempfile
import subprocess
import tkinter.messagebox as messagebox

CURRENT_VERSION = "v1.5.3"

def check_for_updates(root, silent=True):
    def _run():
        import re
        import urllib.request
        
        # 使用加速镜像站的 /releases/latest 页面（非 API）来绕过 403 限制和 GFW
        check_urls = [
            "https://github.com/Xynrin/tiktok-douyin-dl/releases/latest",
            "https://kgithub.com/Xynrin/tiktok-douyin-dl/releases/latest",
        ]
        
        latest_version = None
        for url in check_urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
                with urllib.request.urlopen(req, timeout=8) as resp:
                    final_url = resp.geturl()
                    # 从重定向后的 URL 提取版本号，例如 .../releases/tag/v1.4.1
                    match = re.search(r'/tag/(v\d+\.\d+\.\d+)', final_url)
                    if match:
                        latest_version = match.group(1)
                        break
            except Exception:
                continue
                
        if not latest_version:
            if not silent:
                err_msg = "无法获取最新版本信息。\n\n这通常是因为国内网络波动或加速节点失效。\n请稍后再试或开启全局代理。"
                root.after(0, lambda: messagebox.showerror("网络错误", err_msg, parent=root))
            return
            
        if latest_version != CURRENT_VERSION:
            release_notes = ""
            try:
                # 尝试获取更新日志
                api_url = f"https://api.github.com/repos/Xynrin/tiktok-douyin-dl/releases/tags/{latest_version}"
                req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    body = data.get("body", "").strip()
                    if body:
                        # 限制日志长度
                        if len(body) > 300:
                            body = body[:300] + "...\n(查看更多请前往 Github)"
                        release_notes = f"\n\n【更新日志】\n{body}"
            except Exception:
                pass
                
            msg = f"发现新版本 {latest_version}！\n\n您当前版本为 {CURRENT_VERSION}。{release_notes}\n\n是否立即下载并覆盖更新？\n(国内网络将自动启用加速节点下载)"
            def _show_prompt():
                if messagebox.askyesno("软件更新", msg, parent=root):
                    # 拼接固定的下载链接，并使用国内 ghproxy 加速下载
                    raw_dl_url = f"https://github.com/Xynrin/tiktok-douyin-dl/releases/download/{latest_version}/MediaDownloader_Windows_Setup.zip"
                    proxy_dl_url = f"https://ghp.ci/{raw_dl_url}"
                    _start_download_and_update(root, proxy_dl_url)
            root.after(0, _show_prompt)
        else:
            if not silent:
                root.after(0, lambda: messagebox.showinfo("检查更新", "当前已经是最新版本！", parent=root))

    threading.Thread(target=_run, daemon=True).start()

def _start_download_and_update(root, download_url):
    def _download():
        try:
            import zipfile
            temp_dir = tempfile.gettempdir()
            zip_path = os.path.join(temp_dir, "MediaDownloader_Update.zip")
            setup_path = os.path.join(temp_dir, "MediaDownloader_Setup.exe")
            
            # 创建下载进度窗口
            import tkinter as tk
            from tkinter import ttk
            progress_win = tk.Toplevel(root)
            progress_win.title("软件更新中")
            progress_win.geometry("350x150")
            progress_win.resizable(False, False)
            progress_win.transient(root)
            progress_win.grab_set()
            
            tk.Label(progress_win, text="正在下载最新安装包，请耐心等待...", font=("微软雅黑", 10)).pack(pady=15)
            progress_bar = ttk.Progressbar(progress_win, length=280, mode='determinate')
            progress_bar.pack(pady=5)
            lbl_progress = tk.Label(progress_win, text="0 MB / 0 MB", font=("微软雅黑", 9))
            lbl_progress.pack(pady=5)
            
            # 使用 urlopen 分块下载并更新进度条
            req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                total_size = int(resp.getheader('Content-Length', 0))
                downloaded = 0
                chunk_size = 8192
                with open(zip_path, 'wb') as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            def _update_ui(p=progress, d=downloaded, t=total_size):
                                progress_bar['value'] = p
                                lbl_progress.config(text=f"{d/1024/1024:.1f} MB / {t/1024/1024:.1f} MB")
                            root.after(0, _update_ui)
            
            root.after(0, lambda: lbl_progress.config(text="正在解压..."))
            # 解压 ZIP 文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            root.after(0, progress_win.destroy)
            
            # 准备静默安装 bat 脚本
            bat_path = os.path.join(temp_dir, "update_app.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write("timeout /t 2 /nobreak >nul\n") # 等待主程序关闭
                f.write(f'start "" "{setup_path}" /SILENT\n') # 启动静默安装
            
            def _apply():
                messagebox.showinfo("更新准备完毕", "更新包已下载并解压完毕！点击确定后软件将重启以完成更新。", parent=root)
                subprocess.Popen(bat_path, shell=True)
                sys.exit(0)
            
            root.after(0, _apply)

        except Exception as e:
            def _err():
                try:
                    progress_win.destroy()
                except:
                    pass
                messagebox.showerror("更新失败", f"下载更新包失败：{e}", parent=root)
            root.after(0, _err)
            
    threading.Thread(target=_download, daemon=True).start()
