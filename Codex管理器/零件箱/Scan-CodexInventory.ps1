# Codex 库存扫描器 - 生成桌面仪表盘 HTML
$ErrorActionPreference = 'SilentlyContinue'
$root = "$env:USERPROFILE\.codex"
$out  = Join-Path $PSScriptRoot '库存仪表盘.html'

function Measure-Dir([string]$path) {
    $files = Get-ChildItem $path -Recurse -File -Force -ErrorAction SilentlyContinue
    $md = 0; $size = 0
    foreach ($f in $files) { $size += $f.Length; if ($f.Extension -eq '.md') { $md++ } }
    [pscustomobject]@{ MB = [math]::Round($size/1MB,1); Files = $files.Count; Md = $md }
}

$coreNames    = @('skills','memories','rules')
$managedNames = @('plugins','cache','.sandbox-bin','.sandbox','.sandbox-secrets','sqlite','vendor_imports','node_repl','mcp-oauth-locks','process_manager','thread-writer-locks','ambient-suggestions','browser','computer-use','secrets','pets','shell_snapshots','log')
$junkNames    = @('tmp')
$historyNames = @('sessions','archived_sessions','visualizations','generated_images','attachments','codex-remote-attachments','dictation-history')

$rows = New-Object System.Collections.Generic.List[object]
$catTotals = @{ core=@{MB=0.0;Files=0;Md=0}; managed=@{MB=0.0;Files=0;Md=0}; junk=@{MB=0.0;Files=0;Md=0}; history=@{MB=0.0;Files=0;Md=0}; other=@{MB=0.0;Files=0;Md=0} }

function Add-Row($name, $cat, $m, $note) {
    $rows.Add([pscustomobject]@{ Name=$name; Cat=$cat; MB=$m.MB; Files=$m.Files; Md=$m.Md; Note=$note })
    $catTotals[$cat].MB += $m.MB; $catTotals[$cat].Files += $m.Files; $catTotals[$cat].Md += $m.Md
}

Get-ChildItem $root -Force | ForEach-Object {
    $n = $_.Name
    if (-not $_.PSIsContainer) {
        if ($n -in @('config.toml','AGENTS.md')) {
            $isMd = 0; if ($_.Extension -eq '.md') { $isMd = 1 }
            Add-Row $n 'core' ([pscustomobject]@{MB=[math]::Round($_.Length/1MB,2);Files=1;Md=$isMd}) '正式配置文件'
        }
        return
    }
    if ($n -eq '.tmp') {
        $mManaged = [pscustomobject]@{MB=0.0;Files=0;Md=0}; $mJunk = [pscustomobject]@{MB=0.0;Files=0;Md=0}
        foreach ($s in (Get-ChildItem $_.FullName -Force)) {
            if ($s.Name -in @('bundled-marketplaces','marketplaces')) {
                $mm = Measure-Dir $s.FullName; $mManaged.MB+=$mm.MB; $mManaged.Files+=$mm.Files; $mManaged.Md+=$mm.Md
            } else {
                $mj = Measure-Dir $s.FullName; $mJunk.MB+=$mj.MB; $mJunk.Files+=$mj.Files; $mJunk.Md+=$mj.Md
            }
        }
        Add-Row '.tmp\市场源' 'managed' $mManaged '插件市场源，config.toml 在用，别动'
        if ($mJunk.Files -gt 0) { Add-Row '.tmp\其他残留' 'junk' $mJunk '插件暂存残留，可清' }
        return
    }
    $m = Measure-Dir $_.FullName
    if ($coreNames -contains $n)        { Add-Row $n 'core' $m '正式资产，所有 AI 读它' }
    elseif ($managedNames -contains $n) { Add-Row $n 'managed' $m '系统自管，删了会重建或出错' }
    elseif ($junkNames -contains $n)    { Add-Row $n 'junk' $m '任务残留，可安全清理' }
    elseif ($historyNames -contains $n) { Add-Row $n 'history' $m '聊天历史/生成物，删不删你决定' }
    else { Add-Row $n 'other' $m '未分类，需人工看一眼' }
}

$formalSkills = New-Object System.Collections.Generic.List[object]
Get-ChildItem (Join-Path $root 'skills') -Directory -Force | Where-Object { $_.Name -notlike '.*' } | ForEach-Object {
    $m = Measure-Dir $_.FullName
    $formalSkills.Add([pscustomobject]@{ Name=$_.Name; Md=$m.Md; KB=[math]::Round($m.MB*1024,0) })
}
$systemSkills = (Get-ChildItem (Join-Path $root 'skills\.system') -Directory -Force).Count
$pluginSkillMd = (Get-ChildItem (Join-Path $root 'plugins') -Recurse -Filter 'SKILL.md' -File -Force).Count

$junkMd = $catTotals.junk.Md; $junkMB = [math]::Round($catTotals.junk.MB,1)
$totalMB = 0.0; $totalMd = 0; $totalFiles = 0
foreach ($k in @($catTotals.Keys)) { $totalMB += $catTotals[$k].MB; $totalMd += $catTotals[$k].Md; $totalFiles += $catTotals[$k].Files }
$totalMB = [math]::Round($totalMB,1)

if ($junkMd -gt 50 -or $junkMB -gt 100)     { $status='red';    $statusText='垃圾超标，该清理了' }
elseif ($junkMd -gt 10 -or $junkMB -gt 20)  { $status='yellow'; $statusText='有少量残留，可以清' }
else                                        { $status='green';  $statusText='干净，无需清理' }

$report = [ordered]@{}
$report.generatedAt = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
$report.totalMB = $totalMB
$report.totalFiles = $totalFiles
$report.totalMd = $totalMd
$report.junkMB = $junkMB
$report.junkMd = $junkMd
$report.status = $status
$report.statusText = $statusText
$report.catTotals = $catTotals
$report.dirs = $rows.ToArray()
$report.formalSkills = $formalSkills.ToArray()
$report.systemSkills = $systemSkills
$report.pluginSkillMd = $pluginSkillMd
$json = ($report | ConvertTo-Json -Depth 6 -Compress)

$html = @'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Codex 库存仪表盘</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:"Microsoft YaHei",system-ui,sans-serif; background:#0f1115; color:#e6e8ee; padding:28px; }
  h1 { font-size:22px; margin-bottom:4px; }
  .sub { color:#8a90a0; font-size:13px; margin-bottom:22px; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin-bottom:24px; }
  .card { background:#171a21; border:1px solid #262b36; border-radius:12px; padding:16px 18px; }
  .card .label { font-size:12px; color:#8a90a0; margin-bottom:6px; }
  .card .value { font-size:24px; font-weight:700; }
  .card .hint { font-size:12px; color:#8a90a0; margin-top:4px; }
  .light { display:inline-block; padding:6px 16px; border-radius:999px; font-weight:700; font-size:14px; }
  .green { background:#0e3b26; color:#4ade80; }
  .yellow { background:#3b2f0e; color:#fbbf24; }
  .red { background:#3b0e0e; color:#f87171; }
  h2 { font-size:16px; margin:26px 0 12px; color:#c9cede; }
  table { width:100%; border-collapse:collapse; background:#171a21; border-radius:12px; overflow:hidden; font-size:13px; }
  th,td { padding:10px 14px; text-align:left; border-bottom:1px solid #232833; }
  th { color:#8a90a0; font-weight:600; font-size:12px; }
  tr:last-child td { border-bottom:none; }
  td.num { font-variant-numeric:tabular-nums; text-align:right; }
  .badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:12px; }
  .b-core { background:#12324a; color:#7dd3fc; }
  .b-managed { background:#2a2440; color:#c4b5fd; }
  .b-junk { background:#402a1a; color:#fdba74; }
  .b-history { background:#1a3328; color:#6ee7b7; }
  .b-other { background:#333; color:#ccc; }
  .note { color:#8a90a0; font-size:12px; }
  .skill { display:inline-block; background:#171a21; border:1px solid #262b36; border-radius:8px; padding:8px 14px; margin:0 8px 8px 0; font-size:13px; }
  .skill b { color:#7dd3fc; }
</style>
</head>
<body>
<h1>Codex 库存仪表盘</h1>
<div class="sub">扫描位置：~/.codex ｜ 生成时间：<span id="t"></span></div>
<div id="statusline" style="margin-bottom:18px"></div>
<div class="cards" id="cards"></div>
<h2>各目录明细（按占用排序）</h2>
<table id="tbl"><thead><tr><th>目录</th><th>分类</th><th style="text-align:right">占用 MB</th><th style="text-align:right">文件数</th><th style="text-align:right">md 数</th><th>说明</th></tr></thead><tbody></tbody></table>
<h2>正式 Skills（这些是你的资产）</h2>
<div id="skills"></div>
<div class="note" id="skillnote" style="margin-top:8px"></div>
<script>
const D = __DATA__;
if (!Array.isArray(D.dirs)) D.dirs = D.dirs ? [D.dirs] : [];
if (!Array.isArray(D.formalSkills)) D.formalSkills = D.formalSkills ? [D.formalSkills] : [];
D.dirs.sort((a,b)=>b.MB-a.MB);
const catName = { core:'核心配置', managed:'系统托管', junk:'临时垃圾', history:'历史记录', other:'未分类' };
document.getElementById('t').textContent = D.generatedAt;
document.getElementById('statusline').innerHTML = '<span class="light '+D.status+'">'+D.statusText+'</span> <span class="note" style="margin-left:10px">垃圾区：'+D.junkMd+' 条 md / '+D.junkMB+' MB（阈值：50 条或 100 MB 变红）</span>';
const cards = [
  { label:'总占用', value:D.totalMB.toLocaleString()+' MB', hint:'文件 '+D.totalFiles.toLocaleString()+' 个' },
  { label:'md 总数', value:D.totalMd.toLocaleString(), hint:'含系统托管缓存' },
  { label:'核心配置 md', value:D.catTotals.core.Md, hint:'你的正式资产' },
  { label:'垃圾 md', value:D.junkMd, hint:D.junkMB+' MB' },
];
document.getElementById('cards').innerHTML = cards.map(c=>'<div class="card"><div class="label">'+c.label+'</div><div class="value">'+c.value+'</div><div class="hint">'+c.hint+'</div></div>').join('');
document.querySelector('#tbl tbody').innerHTML = D.dirs.map(d=>'<tr><td>'+d.Name+'</td><td><span class="badge b-'+d.Cat+'">'+catName[d.Cat]+'</span></td><td class="num">'+d.MB.toLocaleString()+'</td><td class="num">'+d.Files.toLocaleString()+'</td><td class="num">'+d.Md.toLocaleString()+'</td><td class="note">'+d.Note+'</td></tr>').join('');
document.getElementById('skills').innerHTML = D.formalSkills.map(s=>'<span class="skill"><b>'+s.Name+'</b> | '+s.Md+' md | '+s.KB+' KB</span>').join('') || '<span class="note">无</span>';
document.getElementById('skillnote').textContent = '另有系统内置 skills '+D.systemSkills+' 个（.system，勿动）；插件缓存里的 SKILL.md 副本 '+D.pluginSkillMd+' 份（插件自带文档，不是垃圾，别手动删）。';
</script>
</body>
</html>
'@

$html = $html.Replace('__DATA__', $json)
[System.IO.File]::WriteAllText($out, $html, [System.Text.UTF8Encoding]::new($true))
Write-Output "仪表盘已生成: $out"
Write-Output "状态: $statusText (垃圾 md=$junkMd, 垃圾 MB=$junkMB)"
