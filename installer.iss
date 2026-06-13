[Setup]
AppName=TikTok & Douyin Downloader
AppVersion=1.0
; 默认安装路径为 Program Files
DefaultDirName={autopf}\MediaDownloader
DefaultGroupName=MediaDownloader
OutputDir=dist
OutputBaseFilename=MediaDownloader_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

; 强制显示选择安装路径页面
DisableDirPage=no

; 指定免责声明/开源协议文件（安装时强制要求勾选“我同意”）
LicenseFile=Disclaimer.txt

; 安装包本身的图标
SetupIconFile=app.ico

; 使用现代化的向导界面风格
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"

[Files]
Source: "dist\MediaDownloader_GUI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "ms-playwright\*"; DestDir: "{userprofile}\.cache\ms-playwright"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Disclaimer.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "app.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MediaDownloader"; Filename: "{app}\MediaDownloader_GUI.exe"; IconFilename: "{app}\app.ico"
Name: "{group}\卸载 MediaDownloader"; Filename: "{uninstallexe}"
Name: "{autodesktop}\MediaDownloader"; Filename: "{app}\MediaDownloader_GUI.exe"; IconFilename: "{app}\app.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\MediaDownloader_GUI.exe"; Description: "启动 MediaDownloader"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
Type: filesandordirs; Name: "{%USERPROFILE}\.cache\ms-playwright"
