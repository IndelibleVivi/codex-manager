$ws = New-Object -ComObject WScript.Shell
$fso = New-Object -ComObject Scripting.FileSystemObject
$desktop = [Environment]::GetFolderPath("Desktop")
$short = $fso.GetFolder($PSScriptRoot).ShortPath
$s1 = $ws.CreateShortcut("$desktop\CodexMgr.lnk")
$s1.TargetPath = "$short\manager.bat"
$s1.WorkingDirectory = $short
$s1.IconLocation = "C:\Windows\System32\imageres.dll,76"
$s1.Description = "打开 Codex 配置管理器"
$s1.Save()
Rename-Item "$desktop\CodexMgr.lnk" "Codex 管理器.lnk" -Force
$s2 = $ws.CreateShortcut("$desktop\CodexDash.lnk")
$s2.TargetPath = "$short\dashboard.bat"
$s2.WorkingDirectory = $short
$s2.IconLocation = "C:\Windows\System32\imageres.dll,102"
$s2.Description = "扫描并打开 Codex 库存报告"
$s2.Save()
Rename-Item "$desktop\CodexDash.lnk" "Codex 库存仪表盘.lnk" -Force
Write-Host ""
Write-Host "安装完成！桌面上多了两个图标：Codex 管理器 / Codex 库存仪表盘" -ForegroundColor Green
Write-Host "这个窗口可以关了。"
pause