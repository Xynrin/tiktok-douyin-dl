import os
import sys
import threading
import urllib.request
import urllib.error
import json
import tempfile
import subprocess
import tkinter.messagebox as messagebox

CURRENT_VERSION = "v1.2.0"
REPO_API_URL = "https://api.github.com/repos/Xynrin/tiktok-douyin-dl/releases/latest"

def check_for_updates(root, silent=True):
    def _run():
        try:
            req = urllib.request.Request(REPO_API_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                
            latest_version = data.get("tag_name", "")
            if latest_version and latest_version.startswith("v") and latest_version != CURRENT_VERSION:
                # 提示更新
                msg = f"发现新版本 {latest_version}！\n\n更新内容:\n{data.get('body', '')}\n\n是否立即下载并更新？"
                def _show_prompt():
                    if messagebox.askyesno("软件更新", msg, parent=root):
                        # 查找 setup 文件下载链接
                        assets = data.get("assets", [])
                        download_url = None
                        for a in assets:
                            if a.get("name", "").endswith("Setup.exe"):
                                download_url = a.get("browser_download_url")
                                break
                        if not download_url:
                            # 降级：如果没有提供 Setup.exe，就在浏览器打开发布页
                            import webbrowser
                            webbrowser.open(data.get("html_url", ""))
                            return
                        _start_download_and_update(root, download_url)
                
                root.after(0, _show_prompt)
            else:
                if not silent:
                    root.after(0, lambda: messagebox.showinfo("检查更新", "当前已经是最新版本！", parent=root))
        except Exception as e:
            if not silent:
                root.after(0, lambda: messagebox.showerror("检查更新失败", f"网络错误：{e}", parent=root))
    
    threading.Thread(target=_run, daemon=True).start()

def _start_download_and_update(root, download_url):
    def _download():
        try:
            temp_dir = tempfile.gettempdir()
            setup_path = os.path.join(temp_dir, "MediaDownloader_Update_Setup.exe")
            
            # 使用 urllib 下载
            req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp, open(setup_path, 'wb') as f:
                f.write(resp.read())
            
            # 准备静默安装 bat 脚本
            bat_path = os.path.join(temp_dir, "update_app.bat")
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write("timeout /t 2 /nobreak >nul\n") # 等待主程序关闭
                f.write(f'start "" "{setup_path}" /SILENT\n') # 启动静默安装
            
            def _apply():
                messagebox.showinfo("更新准备完毕", "更新包已下载完成，点击确定后软件将重启以完成更新。", parent=root)
                subprocess.Popen(bat_path, shell=True)
                sys.exit(0)
            
            root.after(0, _apply)

        except Exception as e:
            root.after(0, lambda: messagebox.showerror("更新失败", f"下载更新包失败：{e}", parent=root))
            
    threading.Thread(target=_download, daemon=True).start()
