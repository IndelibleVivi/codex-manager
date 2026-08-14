# -*- coding: utf-8 -*-
"""Codex 配置管理器 v2"""
import http.server, json, os, shutil, hashlib, urllib.parse, urllib.request, webbrowser, threading, datetime, re, sys

ROOT = os.path.realpath(os.path.expanduser(os.path.join('~', '.codex')))
BASE = os.path.dirname(os.path.abspath(__file__))
QUAR = os.path.join(BASE, '隔离区（删错了来这捞）')
TEXT_EXT = {'.md', '.toml', '.json', '.txt', '.rules', '.yaml', '.yml', '.cfg', '.ini'}
VIEW_CAP = 3 * 1024 * 1024
EDIT_CAP = 512 * 1024
TRANSLATE_URL = 'http://127.0.0.1:10100/v1/chat/completions'
TRANSLATE_MODEL = 'kimi/k3[1m]'

MANAGED = {'plugins','cache','.sandbox-bin','.sandbox','.sandbox-secrets','sqlite','vendor_imports','node_repl','mcp-oauth-locks','process_manager','thread-writer-locks','ambient-suggestions','browser','computer-use','secrets','pets','shell_snapshots','log'}
HISTORY = {'sessions','archived_sessions','visualizations','generated_images','attachments','codex-remote-attachments','dictation-history'}

WARN = {
 'core':    '这是正式配置/记忆，删改会影响所有 AI 的行为。你当然可以动——注意：编辑没有自动备份（删文件才进隔离区），下手前想清楚。',
 'managed': '系统托管文件，删了系统会自动重建（重建前可能报错）。你坚持删我也照办，会进隔离区。',
 'history': '历史记录/生成物，删了之后旧聊天里的图片或可视化可能打不开。',
 'junk':    '垃圾，放心删。',
 'other':   '我不确定这是什么，删之前建议先问阿晋一嘴。',
 'git':     '版本库内部文件：可以看个新鲜，但已锁死，不能改不能删（动了历史版本就全毁了）。',
}
PROV = {'user':'你安装/你写的', 'codex':'Codex 自动生成的', 'system':'系统/插件自带的', 'mixed':'混合工作区'}
PRIO = {'core':0, 'junk':1, 'other':2, 'history':3, 'managed':4, 'git':5}
QUICK_FILES = ['AGENTS.md', 'config.toml', 'rules/default.rules',
               'memories/MEMORY.md', 'memories/memory_summary.md', 'memories/raw_memories.md']

def classify(rel):
    if '.tmp-' in rel:
        return 'junk', 'codex'
    parts = rel.replace('/', os.sep).split(os.sep)
    top = parts[0]
    if '.git' in parts:
        return 'git', 'system'
    if top == 'skills':
        return ('core', 'system') if len(parts) > 1 and parts[1] == '.system' else ('core', 'user')
    if top == 'memories': return 'core', 'codex'
    if top == 'rules': return 'core', 'user'
    if top in ('AGENTS.md', 'config.toml', 'opencodex-catalog.json'): return 'core', 'user'
    if top in MANAGED: return 'managed', 'system'
    if top == 'tmp': return 'junk', 'codex'
    if top == '.tmp':
        if len(parts) < 2:
            return 'managed', 'system'
        if len(parts) > 1 and parts[1] in ('bundled-marketplaces', 'marketplaces'):
            return 'managed', 'system'
        return 'junk', 'codex'
    if top in HISTORY: return 'history', 'codex'
    return 'other', 'mixed'

def safe(rel):
    rel = (rel or '').strip().lstrip('/\\')
    p = os.path.realpath(os.path.join(ROOT, rel))
    if p != ROOT and not p.startswith(ROOT + os.sep):
        return None
    return p

def rel_of(p):
    return os.path.relpath(p, ROOT).replace(os.sep, '/')

def entry(p):
    st = os.stat(p)
    rel = rel_of(p)
    cat, prov = classify(rel)
    is_dir = os.path.isdir(p)
    return {'name': os.path.basename(p), 'path': rel, 'isDir': is_dir,
            'size': 0 if is_dir else st.st_size,
            'mtime': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M'),
            'cat': cat, 'prov': prov}

SKILL_TEMPLATE = '''---
name: {name}
description: （一句话写清楚：这个技能什么时候用。越具体，AI 越会在对的时机调用它）
---

# {name}

## 什么时候用
- 当……的时候

## 怎么做
1. 第一步
2. 第二步

## 注意
- （可选）有什么坑要避开
'''

def do_translate(text, to):
    if len(text) > 20000:
        return {'ok': False, 'error': '内容超过 2 万字符，太长了一次翻不完，可以分段翻'}
    if to == 'zh':
        prompt = '把以下内容翻译成中文。如果内容是代码或配置文件，保持键名和代码原样，在每段下方用中文解释它的作用；如果是普通文章，直接输出流畅的中文译文。不要输出额外说明：' + chr(10) + chr(10) + text
    else:
        prompt = 'Translate the following content into English. Keep markdown formatting unchanged. Output only the translation, no explanations:' + chr(10) + chr(10) + text
    body = json.dumps({'model': TRANSLATE_MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'stream': False}).encode('utf-8')
    req = urllib.request.Request(TRANSLATE_URL, data=body,
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer none'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode('utf-8'))
        out = d.get('choices', [{}])[0].get('message', {}).get('content', '')
        if not out:
            return {'ok': False, 'error': '翻译代理返回了空结果'}
        return {'ok': True, 'text': out}
    except Exception as e:
        return {'ok': False, 'error': '翻译引擎没响应（本机 10100 代理可能没开）：' + str(e)}
HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Codex 配置管理器</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family:"Microsoft YaHei",system-ui,sans-serif; background:#0f1115; color:#e6e8ee; height:100vh; display:flex; flex-direction:column; }
  header { padding:14px 24px; border-bottom:1px solid #262b36; display:flex; align-items:center; gap:16px; }
  header h1 { font-size:18px; }
  .tabs { display:flex; gap:8px; }
  .tab { padding:6px 16px; border-radius:8px; background:#171a21; border:1px solid #262b36; cursor:pointer; font-size:13px; color:#c9cede; }
  .tab.on { background:#12324a; border-color:#2b5a7a; color:#7dd3fc; }
  main { flex:1; display:flex; overflow:hidden; }
  #left { width:430px; border-right:1px solid #262b36; overflow-y:auto; padding:12px; }
  #right { flex:1; overflow-y:auto; padding:16px 20px; }
  .crumb { font-size:12px; color:#8a90a0; padding:6px 4px; cursor:pointer; }
  .sect { font-size:12px; color:#fbbf24; padding:10px 4px 4px; font-weight:700; }
  .row { display:flex; align-items:center; gap:8px; padding:7px 10px; border-radius:8px; cursor:pointer; font-size:13px; }
  .row:hover { background:#1c2029; }
  .row .nm { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .badge { display:inline-block; padding:1px 8px; border-radius:999px; font-size:11px; flex-shrink:0; }
  .b-core { background:#12324a; color:#7dd3fc; }
  .b-managed { background:#2a2440; color:#c4b5fd; }
  .b-junk { background:#402a1a; color:#fdba74; }
  .b-history { background:#1a3328; color:#6ee7b7; }
  .b-other,.b-git { background:#333; color:#ccc; }
  .prov { font-size:11px; color:#667; flex-shrink:0; }
  .warn { display:none !important; }
  .warn-off { padding:12px 14px; border-radius:10px; font-size:13px; margin-bottom:12px; line-height:1.6; }
  .w-core { background:#12324a33; border:1px solid #2b5a7a; }
  .w-managed { background:#2a244033; border:1px solid #4a3f7a; }
  .w-junk { background:#402a1a33; border:1px solid #7a5a2b; }
  .w-history { background:#1a332833; border:1px solid #2b7a5a; }
  .w-other,.w-git { background:#33333333; border:1px solid #555; }
  pre { background:#171a21; border:1px solid #262b36; border-radius:10px; padding:14px; font-size:12.5px; line-height:1.7; white-space:pre-wrap; word-break:break-all; max-height:55vh; overflow-y:auto; }
  textarea { width:100%; height:50vh; background:#171a21; color:#e6e8ee; border:1px solid #2b5a7a; border-radius:10px; padding:14px; font-size:12.5px; font-family:Consolas,monospace; line-height:1.7; }
  button { padding:7px 18px; border-radius:8px; border:1px solid #262b36; background:#1c2029; color:#e6e8ee; cursor:pointer; font-size:13px; margin-right:8px; }
  button:hover { background:#262c38; }
  button.danger { border-color:#7a2b2b; color:#f87171; }
  button.primary { border-color:#2b5a7a; background:#12324a; color:#7dd3fc; }
  button.i18n { border-color:#2b7a5a; color:#6ee7b7; }
  .btnbar { margin:12px 0; }
  .path { font-size:12px; color:#8a90a0; margin-bottom:8px; word-break:break-all; }
  .dup { background:#171a21; border:1px solid #262b36; border-radius:10px; padding:12px 14px; margin-bottom:12px; }
  .dup .p { display:flex; align-items:center; gap:8px; font-size:12.5px; padding:4px 0; }
  .dup .p span { flex:1; word-break:break-all; }
  .row.sel { background:#12324a; }
  .row.sel .nm { color:#7dd3fc; }
  .grpbtn { padding:1px 10px; font-size:11px; margin-left:8px; }
  .trash { color:#8a90a0; font-size:12px; padding:0 4px; }
  .trash:hover { color:#f87171; }
  .kids { margin-left:22px; border-left:1px solid #262b36; padding-left:6px; }
  .hidden { display:none !important; }
  .toast { position:fixed; top:16px; right:16px; background:#12324a; border:1px solid #2b5a7a; padding:10px 18px; border-radius:10px; font-size:13px; z-index:9; max-width:400px; }
  input { background:#171a21; border:1px solid #262b36; border-radius:8px; color:#e6e8ee; padding:8px 12px; font-size:13px; width:280px; }
  h3 { font-size:14px; color:#c9cede; margin:16px 0 8px; }
  .trans { margin-top:12px; }
  .trans .t-head { font-size:12px; color:#6ee7b7; margin-bottom:6px; }
</style>
</head>
<body>
<header>
  <h1>Codex 配置管理器</h1>
  <div class="tabs">
    <div class="tab on" data-t="files">📁 文件管理</div>
    <div class="tab" data-t="dups">🔍 md 查重</div>
    <div class="tab" data-t="newskill">➕ 新建 Skill</div>
    <div class="tab" data-t="trash">🗑 回收站</div>
  </div>
  <span style="font-size:12px;color:#667;margin-left:auto">~/.codex</span>
</header>
<main>
  <div id="left">
    <div class="crumb" id="crumb">📂 根目录</div>
    <div id="list"></div>
  </div>
  <div id="right">
    <div id="pane-files"><div style="color:#667;font-size:13px;padding:40px;text-align:center">← 点左边的文件查看内容<br>⭐ 重要文件在最上面，不用一层层钻<br><br>🔵核心配置 ｜ 🟣系统托管 ｜ 🟠垃圾 ｜ 🟢历史记录<br><br>删除不消失，全部进「隔离区」可捞回</div></div>
    <div id="pane-dups" class="hidden">
      <button class="primary" onclick="runDups()">开始查重（按内容找重复 md）</button>
      <div id="dupout" style="margin-top:14px"></div>
    </div>
    <div id="pane-newskill" class="hidden">
      <h3>新建一个 Skill（格式已固定，你只需填空）</h3>
      <div style="margin:10px 0">技能名（小写字母/数字/连字符）：<input id="skname" placeholder="例如 my-cleanup"></div>
      <h3>格式模板预览</h3>
      <pre id="sktpl"></pre>
      <div id="skerr" style="font-size:13px;margin:8px 0;min-height:18px"></div>
      <div style="text-align:right"><button class="primary" onclick="createSkill()" style="padding:10px 36px;font-size:14px">保存</button></div>
    </div>    <div id="pane-trash" class="hidden">
      <div style="color:#8a90a0;font-size:13px;margin-bottom:8px">删掉的东西都在这儿躺着，7 天后自动彻底删除。恢复 = 放回原位。</div>
      <div id="trashout"></div>
    </div>
  </div>
</main>
<script>
window.onerror=function(m,s,l,c){var el=document.getElementById('list');if(el)el.innerHTML='<div style="color:#f87171;padding:10px;font-size:12px">JS err: '+m+' @'+l+':'+c+'</div>';};
const catName={core:'核心配置',managed:'系统托管',junk:'临时垃圾',history:'历史记录',other:'未分类',git:'已上锁'};
function selRow(r){document.querySelectorAll('.row.sel').forEach(x=>x.classList.remove('sel'));r.classList.add('sel');}
let curDir='',curFile=null,editing=false;
async function api(u,opt){const r=await fetch(u,opt);return r.json();}
function toast(m){const d=document.createElement('div');d.className='toast';d.textContent=m;document.body.appendChild(d);setTimeout(()=>d.remove(),3200);}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));t.classList.add('on');
  const k=t.dataset.t;
  document.getElementById('pane-files').classList.toggle('hidden',k!=='files');
  document.getElementById('pane-dups').classList.toggle('hidden',k!=='dups');
  document.getElementById('pane-newskill').classList.toggle('hidden',k!=='newskill');
  document.getElementById('pane-trash').classList.toggle('hidden',k!=='trash');
  if(k==='newskill')loadTpl();if(k==='trash')loadTrash();
});
function mkRow(e){
  const r=document.createElement('div');r.className='row';
  r.innerHTML='<span class="nm">'+(e.isDir?'📁 ':'📄 ')+e.name+'</span><span class="badge b-'+e.cat+'">'+catName[e.cat]+'</span><span class="prov">'+(e.isDir?'':(e.size/1024).toFixed(1)+'KB')+'</span>';
  r.onclick=()=>{if(e.isDir){loadDir(e.path)}else{selRow(r);openFile(e.path)}};
  return r;
}
async function loadDir(p){
  curDir=p;
  document.getElementById('crumb').textContent='📂 '+(p||'总览');
  document.getElementById('crumb').onclick=()=>{const i=p.lastIndexOf('/');loadDir(i>0?p.slice(0,i):'');};
  const d=await api('/api/list?path='+encodeURIComponent(p));
  const el=document.getElementById('list');
  el.innerHTML='';
  if(p){
    const up=document.createElement('div');up.className='row';up.innerHTML='<span class="nm">⬅️ 返回上一层</span>';up.onclick=()=>{const i=p.lastIndexOf('/');loadDir(i>0?p.slice(0,i):'');};el.appendChild(up);
    d.entries.forEach(e=>el.appendChild(mkRow(e)));
    return;
  }
  const desc={'AGENTS.md':'自定义指令：你和 AI 的相处规则','config.toml':'主设置：模型、插件开关都在这','default.rules':'行为规则','opencodex-catalog.json':'模型目录（OpenCodex 生成）','MEMORY.md':'记忆注册表（找记忆的索引）','memory_summary.md':'记忆总览','raw_memories.md':'原始记忆仓库','memories':'全部记忆文件','extensions':'记忆扩展区（人机合写）','rollout_summaries':'每次任务的总结存档','skills':'你安装的技能','rules':'行为规则目录','grill-me':'拷问模式：AI 连环追问你的计划直到漏洞无处可藏','grilling':'压力测试你的想法，AI 不停反问','.system':'系统内置技能（别动）','imagegen':'系统技能：画图','openai-docs':'系统技能：OpenAI 文档问答','plugin-creator':'系统技能：创建插件','review-agent':'系统技能：代码审查','skill-creator':'系统技能：创建新技能','skill-installer':'系统技能：安装技能','.codex-system-skills.marker':'系统标记文件','sessions':'聊天记录存档','archived_sessions':'旧聊天归档','visualizations':'生成的可视化页面','generated_images':'生成的图片','attachments':'聊天附件','codex-remote-attachments':'远程附件','dictation-history':'语音输入历史','plugins':'插件缓存（系统自装自管）','cache':'系统缓存','.sandbox-bin':'沙盒运行环境','.sandbox':'沙盒数据','.sandbox-secrets':'沙盒密钥','sqlite':'小数据库','.tmp':'插件市场源+临时残留','tmp':'任务临时残留','worktrees':'Haven 等项目的工作区副本','browser':'浏览器数据','computer-use':'电脑控制组件','mcp-oauth-locks':'MCP 登录锁','node_repl':'JS 运行环境','pets':'小彩蛋','process_manager':'进程管理','secrets':'密钥','thread-writer-locks':'写入锁','ambient-suggestions':'建议功能数据','vendor_imports':'第三方组件','shell_snapshots':'终端快照','log':'日志','auth.json':'登录凭证（千万别删！）','models_cache.json':'模型信息缓存','session_index.jsonl':'会话索引','transcription-history.jsonl':'语音转写历史','external_agent_session_imports.json':'外部会话导入记录','installation_id':'安装标识','cap_sid':'系统标识','opencodex.config.toml':'OpenCodex 的配置','opencodex-journal.json':'OpenCodex 的日志'};
  function descFor(n){
    if(desc[n])return desc[n];
    if(n.indexOf('.sqlite')>-1)return '系统数据库文件';
    if(n.indexOf('.bak')>-1)return '配置备份';
    if(n.indexOf('migration')>-1)return '迁移标记（升级留下的）';
    if(n.indexOf('.tmp-')>-1)return '状态临时残留';
    if(n.indexOf('opencodex')>-1)return 'OpenCodex 的组件';
    return '';
  }
  function makeRow(e,canTrash){
    const r=document.createElement('div');r.className='row';
    const dd=descFor(e.name);
    r.innerHTML='<span class="nm">'+(e.isDir?'📁 ':'📄 ')+e.name+(dd?' <span style="color:#889;font-size:11px">— '+dd+'</span>':'')+'</span><span class="prov">'+(e.isDir?'':(e.size/1024).toFixed(1)+'KB')+'</span>';
    if(canTrash){
      const t=document.createElement('span');t.className='trash';t.textContent='🗑';
      t.onclick=async(ev)=>{ev.stopPropagation();if(!confirm('删除 '+e.name+'？进隔离区可捞回。'))return;const rr=await api('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:e.path})});toast(rr.ok?'已移入隔离区':('失败：'+rr.error));if(rr.ok)r.remove();};
      r.appendChild(t);
    }
    if(e.isDir){
      let kidBox=null;
      r.onclick=async()=>{
        if(kidBox){const vis=kidBox.style.display!=='none';kidBox.style.display=vis?'none':'block';return;}
        kidBox=document.createElement('div');kidBox.className='kids';kidBox.innerHTML='<div style="color:#667;font-size:12px;padding:4px">展开中…</div>';
        r.after(kidBox);
        const kd=await api('/api/list?path='+encodeURIComponent(e.path));
        kidBox.innerHTML='';
        kd.entries.slice(0,100).forEach(k=>kidBox.appendChild(makeRow(k,false)));
        if(kd.entries.length>100){const more=document.createElement('div');more.className='row';more.innerHTML='<span class="nm" style="color:#667">… 共 '+kd.entries.length+' 项，只显示前 100</span>';kidBox.appendChild(more);}
      };
    } else {
      r.onclick=()=>{selRow(r);openFile(e.path)};
    }
    return r;
  }
  const groupDef=[
    {key:'配置',title:'📄 配置文件',items:[],open:true,clean:null},
    {key:'skill',title:'🎓 你的 Skills',items:[],open:true,clean:null},
    {key:'记忆',title:'🧠 记忆系统',items:[],open:true,clean:null},
    {key:'junk',title:'🟠 临时垃圾（可以清）',items:[],open:false,clean:'junk'},
    {key:'history',title:'🟢 历史记录（删不删你定）',items:[],open:false,clean:'history'},
    {key:'managed',title:'🟣 系统托管（别手动删）',items:[],open:false,clean:null},
    {key:'other',title:'⚪ 未分类',items:[],open:false,clean:null},
  ];
  const q=await api('/api/quick');
  q.files.forEach(f=>{if(f.group==='skill')return;const g=groupDef.find(x=>x.key===f.group);if(g)g.items.push({name:f.label,path:f.path,size:f.size,isDir:false,cat:'core'});});
  const skl=await api('/api/list?path=skills');
  skl.entries.forEach(e=>groupDef[1].items.push(e));
  const coreDirMap={'memories':'记忆','rules':'配置'};
  d.entries.forEach(e=>{
    if(e.name==='skills')return;
    if(e.cat==='core'&&!e.isDir){const g=groupDef[0];if(!g.items.find(x=>x.name===e.name))g.items.push(e);return;}
    if(e.cat==='core'&&e.isDir){const g=groupDef.find(x=>x.key===coreDirMap[e.name])||groupDef[6];g.items.push(e);return;}
    const g=groupDef.find(x=>x.key===e.cat)||groupDef[6];
    g.items.push(e);
  });
  groupDef.forEach(g=>{
    if(!g.items.length)return;
    const h=document.createElement('div');h.className='sect';h.style.cursor='pointer';
    const lbl=document.createElement('span');
    lbl.textContent=(g.open?'▾ ':'▸ ')+g.title+'（'+g.items.length+'）';
    h.appendChild(lbl);
    const box=document.createElement('div');
    box.style.display=g.open?'block':'none';
    h.onclick=()=>{const open=box.style.display!=='none';box.style.display=open?'none':'block';lbl.textContent=(open?'▸ ':'▾ ')+g.title+'（'+g.items.length+'）';};
    if(g.clean){
      const cb=document.createElement('button');cb.className='grpbtn danger';cb.textContent='🧹 一键清理';
      cb.onclick=async(ev)=>{ev.stopPropagation();const warn=g.clean==='junk'?'确定清空全部临时垃圾？（进隔离区可捞回）':'确定清空全部历史记录？包括旧聊天归档和生成的图片（进隔离区可捞回，但旧聊天里的图会打不开，想清楚！）';if(!confirm(warn))return;toast('清理中…');const rr=await api('/api/clean_group',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cat:g.clean})});toast(rr.ok?('已清理 '+rr.moved+' 项，全在隔离区'):('失败：'+rr.error));loadDir('');};
      h.appendChild(cb);
    }
    g.items.forEach(e=>box.appendChild(makeRow(e,!!g.clean)));
    el.appendChild(h);el.appendChild(box);
  });
}

async function openFile(p){
  const d=await api('/api/file?path='+encodeURIComponent(p));
  const pane=document.getElementById('pane-files');
  if(d.error){pane.innerHTML='<div class="warn w-other">'+d.error+'</div>';return;}
  curFile=p;editing=false;
  pane.innerHTML='<div class="path">'+p+' ｜ '+catName[d.cat]+' ｜ '+(d.provText||'')+(d.readonly?' ｜ 🔒只读':'')+'</div>'
    +'<div class="warn w-'+d.cat+'">'+d.warn+'</div>'
    +'<div class="btnbar">'
    +(d.editable?'<button class="primary" id="bEdit">✏️ 编辑</button>':'')
    +'<button class="i18n" id="bTrans">🌐 翻译成中文看看</button>'
    +(d.deletable?'<button class="danger" id="bDel">🗑️ 删除（进隔离区）</button>':'')
    +'</div><pre id="viewer"></pre><div id="transbox"></div>';
  document.getElementById('viewer').textContent=d.content;
  document.getElementById('bTrans').onclick=()=>runTranslate(d.content,'zh');
  if(d.editable)document.getElementById('bEdit').onclick=()=>{
    if(editing)return;editing=true;
    const v=document.getElementById('viewer');
    const ta=document.createElement('textarea');ta.value=v.textContent;v.replaceWith(ta);
    const b=document.getElementById('bEdit');b.textContent='💾 保存';
    const tb=document.getElementById('bTrans');tb.textContent='🌐 把框里文字译成英文';
    tb.onclick=async()=>{
      toast('翻译中，稍等…');
      const r=await api('/api/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:ta.value,to:'en'})});
      if(r.ok){ta.value=r.text;toast('已译成英文，检查一遍再保存');}
      else toast(r.error);
    };
    b.onclick=async()=>{
      const r=await api('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:curFile,content:ta.value})});
      toast(r.ok?'已保存':('保存失败：'+r.error));
      if(r.ok)openFile(curFile);
    };
  };
  if(d.deletable)document.getElementById('bDel').onclick=async()=>{
    if(!confirm('确定删除？文件会进隔离区，可以捞回来。'))return;
    const r=await api('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:curFile})});
    toast(r.ok?'已移入隔离区':('删除失败：'+r.error));
    if(r.ok)loadDir(curDir);
  };
}
async function runTranslate(text,to){
  const box=document.getElementById('transbox');
  box.innerHTML='<div class="trans"><div class="t-head">🌐 翻译中，内容多的话要等几十秒…</div></div>';
  const r=await api('/api/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,to})});
  if(r.ok){
    box.innerHTML='<div class="trans"><div class="t-head">🌐 中文翻译（只是预览，不会改动原文件）：</div><pre></pre></div>';
    box.querySelector('pre').textContent=r.text;
  } else {
    box.innerHTML='<div class="trans"><div class="t-head" style="color:#f87171">'+r.error+'</div></div>';
  }
}
async function runDups(){
  document.getElementById('dupout').innerHTML='扫描中，稍等…';
  const d=await api('/api/dups');
  const out=document.getElementById('dupout');
  if(!d.groups.length){out.innerHTML='<div style="color:#6ee7b7;padding:20px">🎉 没有发现内容重复的 md</div>';return;}
  out.innerHTML='<h3>发现 '+d.groups.length+' 组重复</h3>'+d.groups.map((g,gi)=>
    '<div class="dup"><div style="font-size:12px;color:#8a90a0;margin-bottom:6px">第 '+(gi+1)+' 组（'+g.paths.length+' 份相同内容，'+(g.size/1024).toFixed(1)+'KB/份）</div>'
    +g.paths.map(p=>'<div class="p"><span>'+p+'</span><button class="danger" data-p="'+p+'">删这份</button></div>').join('')+'</div>').join('');
  out.querySelectorAll('button[data-p]').forEach(b=>b.onclick=()=>delDup(b.dataset.p));
}
async function delDup(p){
  if(!confirm('删除 '+p+'？进隔离区可捞回。'))return;
  const r=await api('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:p})});
  toast(r.ok?'已移入隔离区':('失败：'+r.error));runDups();
}
async function loadTpl(){
  const d=await api('/api/skill_template');
  const t=d.template;
  const i=t.indexOf('---',4);
  const head=t.slice(0,i+3);
  const bodyT=t.slice(i+3);
  document.getElementById('sktpl').textContent=head+String.fromCharCode(10)+'# ✏️ 下面是正文举例：这几个小标题只是参考结构，按自己的想法写就行，不强制 👇'+String.fromCharCode(10)+bodyT;
}
async function createSkill(){
  const err=document.getElementById('skerr');err.style.color='#f87171';err.textContent='';
  const name=document.getElementById('skname').value.trim();
  const r=await api('/api/new_skill',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
  if(!r.ok){err.textContent='❌ '+r.error;return;}
  err.style.color='#4ade80';err.textContent='✅ 已创建，正在打开编辑…';
  setTimeout(()=>{document.querySelector('.tab').click();openFile('skills/'+name+'/SKILL.md');},800);
}async function loadTrash(){
  const box=document.getElementById('trashout');
  box.innerHTML='读取中…';
  const d=await api('/api/quarantine');
  if(!d.items.length){box.innerHTML='<div style="color:#6ee7b7;padding:20px">回收站是空的 ✨</div>';return;}
  box.innerHTML='<div style="margin:10px 0;color:#8a90a0;font-size:12px">共 '+d.items.length+' 项 ｜ 超过 7 天自动彻底删除 ｜ <button class="danger grpbtn" id="bEmpty">全部清空</button></div>'
    + d.items.map(it=>'<div class="row"><span class="nm">'+(it.isDir?'📁 ':'📄 ')+it.orig+' <span style="color:#667;font-size:11px">删于 '+it.ts+' ｜ 剩 '+it.daysLeft+' 天</span></span><span class="prov">'+(it.size/1024).toFixed(1)+'KB</span><button class="primary grpbtn" data-r="'+it.file+'">恢复</button><button class="danger grpbtn" data-d="'+it.file+'">彻底删</button></div>').join('');
  box.querySelectorAll('button[data-r]').forEach(b=>b.onclick=async()=>{const r=await api('/api/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file:b.dataset.r})});toast(r.ok?'已恢复到原位置':('恢复失败：'+r.error));loadTrash();});
  box.querySelectorAll('button[data-d]').forEach(b=>b.onclick=async()=>{if(!confirm('彻底删除，捞不回来，确定？'))return;const r=await api('/api/purge_item',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file:b.dataset.d})});toast(r.ok?'已彻底删除':('失败：'+r.error));loadTrash();});
  document.getElementById('bEmpty').onclick=async()=>{if(!confirm('清空回收站？全部彻底删除，捞不回来！'))return;await api('/api/empty_quarantine',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});toast('已清空');loadTrash();};
}
loadDir('');;
</script>
</body>
</html>'''


def quar_items():
    items = []
    if not os.path.isdir(QUAR):
        return items
    cutoff = datetime.datetime.now() - datetime.timedelta(days=7)
    for n in sorted(os.listdir(QUAR), reverse=True):
        p = os.path.join(QUAR, n)
        m = re.match(r'(\d{8}-\d{6})__(.*)', n)
        orig = n
        ts = None
        if m:
            try:
                ts = datetime.datetime.strptime(m.group(1), '%Y%m%d-%H%M%S')
            except Exception:
                ts = None
            orig = m.group(2).replace('__', '/')
        if ts is None:
            ts = datetime.datetime.fromtimestamp(os.path.getmtime(p))
        if ts < cutoff:
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            except Exception:
                pass
            continue
        size = 0
        if os.path.isfile(p):
            size = os.path.getsize(p)
        else:
            for dp, _, fns in os.walk(p):
                for fn in fns:
                    try:
                        size += os.path.getsize(os.path.join(dp, fn))
                    except Exception:
                        pass
        days_left = 7 - (datetime.datetime.now() - ts).days
        items.append({'file': n, 'orig': orig, 'ts': ts.strftime('%m-%d %H:%M'), 'size': size, 'isDir': os.path.isdir(p), 'daysLeft': max(days_left, 0)})
    return items

def quar_safe_name(n):
    return re.fullmatch(r'[^/\\]+', n or '') is not None

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def sendj(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def read_body(self):
        try:
            ln = int(self.headers.get('Content-Length', 0))
            return json.loads(self.rfile.read(ln) or b'{}')
        except Exception:
            return {}
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == '/':
            b = HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif u.path == '/api/list':
            rel = q.get('path', [''])[0]
            p = safe(rel)
            if p is None or not os.path.isdir(p):
                return self.sendj({'entries': [], 'error': 'bad path'}, 400)
            try:
                items = [entry(os.path.join(p, n)) for n in os.listdir(p)]
            except Exception as e:
                return self.sendj({'entries': [], 'error': str(e)})
            items.sort(key=lambda e: (PRIO.get(e['cat'], 2), not e['isDir'], e['name'].lower()))
            self.sendj({'entries': items[:800]})
        elif u.path == '/api/quick':
            out = []
            for rel in QUICK_FILES[:3]:
                p = safe(rel)
                if p and os.path.isfile(p):
                    out.append({'label': os.path.basename(rel), 'path': rel, 'size': os.path.getsize(p), 'group': '配置'})
            sk = os.path.join(ROOT, 'skills')
            if os.path.isdir(sk):
                for name in sorted(os.listdir(sk)):
                    f = os.path.join(sk, name, 'SKILL.md')
                    if not name.startswith('.') and os.path.isfile(f):
                        out.append({'label': name, 'path': 'skills/' + name + '/SKILL.md', 'size': os.path.getsize(f), 'group': 'skill'})
            for rel in QUICK_FILES[3:]:
                p = safe(rel)
                if p and os.path.isfile(p):
                    out.append({'label': os.path.basename(rel), 'path': rel, 'size': os.path.getsize(p), 'group': '记忆'})
            self.sendj({'files': out})
        elif u.path == '/api/file':
            rel = q.get('path', [''])[0]
            p = safe(rel)
            if p is None or not os.path.isfile(p):
                return self.sendj({'error': '文件不存在'})
            cat, prov = classify(rel)
            ext = os.path.splitext(p)[1].lower()
            size = os.path.getsize(p)
            if cat == 'git':
                if size > 64 * 1024:
                    return self.sendj({'error': '版本库内部文件，这个比较大就不打开了。反正已上锁，看看目录结构就好。'})
                try:
                    with open(p, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                except Exception:
                    return self.sendj({'error': '这是个二进制文件，没法用文本方式打开。已上锁，不用管它。'})
                return self.sendj({'content': content, 'cat': cat, 'warn': WARN[cat],
                                   'provText': PROV.get(prov, ''), 'editable': False, 'deletable': False, 'readonly': True})
            if ext not in TEXT_EXT:
                return self.sendj({'error': '不是文本文件（' + (ext or '无扩展名') + '），不支持查看编辑。'})
            if size > VIEW_CAP:
                return self.sendj({'error': '文件超过 3MB，太大打不开。'})
            try:
                with open(p, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception as e:
                return self.sendj({'error': '读取失败：' + str(e)})
            editable = size <= EDIT_CAP
            warn = WARN[cat]
            if not editable:
                warn = '这个文件超过 512KB，可以随便看，但太大不允许在这里编辑（怕卡死也怕改错）。要改的话叫阿晋来弄。'
            self.sendj({'content': content, 'cat': cat, 'warn': warn,
                        'provText': PROV.get(prov, ''), 'editable': editable, 'deletable': True,
                        'readonly': not editable})
        elif u.path == '/api/dups':
            hashes = {}
            for dp, dns, fns in os.walk(ROOT):
                if '.git' in dp.replace(os.sep, '/').split('/'):
                    continue
                dns[:] = [d for d in dns if d != '.git']
                for fn in fns:
                    if not fn.lower().endswith('.md'):
                        continue
                    fp = os.path.join(dp, fn)
                    try:
                        if os.path.getsize(fp) > 2 * 1024 * 1024:
                            continue
                        with open(fp, 'rb') as f:
                            h = hashlib.sha1(f.read()).hexdigest()
                        hashes.setdefault(h, []).append(fp)
                    except Exception:
                        pass
            groups = []
            for h, paths in hashes.items():
                if len(paths) > 1:
                    groups.append({'paths': sorted(rel_of(x) for x in paths),
                                   'size': os.path.getsize(paths[0])})
            groups.sort(key=lambda g: -len(g['paths']))
            self.sendj({'groups': groups[:100]})
        elif u.path == '/api/skill_template':
            self.sendj({'template': SKILL_TEMPLATE.replace('{name}', '你的技能名')})
        elif u.path == '/api/quarantine':
            self.sendj({'items': quar_items()})
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        body = self.read_body()
        if u.path == '/api/save':
            rel = body.get('path', '')
            p = safe(rel)
            if p is None or not os.path.isfile(p):
                return self.sendj({'ok': False, 'error': '路径无效'})
            cat, _ = classify(rel)
            if cat == 'git':
                return self.sendj({'ok': False, 'error': '版本库已上锁'})
            if os.path.getsize(p) > EDIT_CAP:
                return self.sendj({'ok': False, 'error': '文件超过 512KB，不允许在此编辑'})
            try:
                with open(p, 'w', encoding='utf-8', newline='') as f:
                    f.write(body.get('content', ''))
                self.sendj({'ok': True})
            except Exception as e:
                self.sendj({'ok': False, 'error': str(e)})
        elif u.path == '/api/delete':
            rel = body.get('path', '')
            p = safe(rel)
            if p is None or not os.path.exists(p):
                return self.sendj({'ok': False, 'error': '路径无效'})
            cat, _ = classify(rel)
            if cat == 'git':
                return self.sendj({'ok': False, 'error': '版本库已上锁，不可删除'})
            try:
                os.makedirs(QUAR, exist_ok=True)
                ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
                shutil.move(p, os.path.join(QUAR, ts + '__' + rel.replace('/', '__')))
                self.sendj({'ok': True})
            except Exception as e:
                self.sendj({'ok': False, 'error': str(e)})
        elif u.path == '/api/translate':
            text = body.get('text', '')
            to = body.get('to', 'zh')
            self.sendj(do_translate(text, to))
        elif u.path == '/api/restore':
            fn = body.get('file', '')
            if not quar_safe_name(fn):
                return self.sendj({'ok': False, 'error': '文件名无效'})
            src = os.path.join(QUAR, fn)
            m = re.match(r'\d{8}-\d{6}__(.*)', fn)
            orig = (m.group(1) if m else fn).replace('__', '/')
            dest = safe(orig)
            if not os.path.exists(src) or dest is None:
                return self.sendj({'ok': False, 'error': '找不到这个文件'})
            if os.path.exists(dest):
                return self.sendj({'ok': False, 'error': '原位置已经有同名文件了，先把那个挪走'})
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.move(src, dest)
                self.sendj({'ok': True})
            except Exception as e:
                self.sendj({'ok': False, 'error': str(e)})
        elif u.path == '/api/purge_item':
            fn = body.get('file', '')
            if not quar_safe_name(fn):
                return self.sendj({'ok': False, 'error': '文件名无效'})
            src = os.path.join(QUAR, fn)
            try:
                if os.path.isdir(src):
                    shutil.rmtree(src)
                elif os.path.exists(src):
                    os.remove(src)
                self.sendj({'ok': True})
            except Exception as e:
                self.sendj({'ok': False, 'error': str(e)})
        elif u.path == '/api/empty_quarantine':
            n = 0
            for x in os.listdir(QUAR):
                p = os.path.join(QUAR, x)
                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p)
                    else:
                        os.remove(p)
                    n += 1
                except Exception:
                    pass
            self.sendj({'ok': True, 'moved': n})
        elif u.path == '/api/clean_group':
            cat = body.get('cat', '')
            if cat not in ('junk', 'history'):
                return self.sendj({'ok': False, 'error': '只允许清理垃圾和历史记录'})
            moved = 0
            errors = []
            os.makedirs(QUAR, exist_ok=True)
            for n in os.listdir(ROOT):
                rel = n
                c2, _ = classify(rel)
                if cat == 'junk' and '.tmp-' in n:
                    c2 = 'junk'
                if c2 != cat:
                    continue
                p = os.path.join(ROOT, n)
                try:
                    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
                    shutil.move(p, os.path.join(QUAR, ts + '__' + n))
                    moved += 1
                except Exception as e:
                    errors.append(n + ': ' + str(e))
            self.sendj({'ok': True, 'moved': moved, 'errors': errors})
        elif u.path == '/api/new_skill':
            name = (body.get('name') or '').strip()
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,40}', name):
                return self.sendj({'ok': False, 'error': '技能名只能用小写字母、数字、连字符（2-41 位），AI 会认不出别的格式'})
            d = os.path.join(ROOT, 'skills', name)
            if os.path.exists(d):
                return self.sendj({'ok': False, 'error': '这个名字已经被占了，换一个'})
            desc = ((body.get('desc') or '').strip() or '（一句话写清楚：这个技能什么时候用。越具体，AI 越会在对的时机调用它）').replace(chr(10), ' ')
            skbody = (body.get('body') or '').strip()
            if skbody:
                content = '---' + chr(10) + 'name: ' + name + chr(10) + 'description: ' + desc + chr(10) + '---' + chr(10) + chr(10) + skbody + chr(10)
            else:
                content = SKILL_TEMPLATE.replace('{name}', name)
            try:
                os.makedirs(d)
                with open(os.path.join(d, 'SKILL.md'), 'w', encoding='utf-8', newline='') as fp:
                    fp.write(content)
                self.sendj({'ok': True})
            except Exception as e:
                self.sendj({'ok': False, 'error': '写入失败：' + str(e)})
        else:
            self.send_response(404); self.end_headers()

def main():
    os.makedirs(QUAR, exist_ok=True)
    try:
        urllib.request.urlopen('http://127.0.0.1:8799/api/skill_template', timeout=1)
        webbrowser.open('http://127.0.0.1:8799/')
        print('already running, browser opened')
        return
    except Exception:
        pass
    srv = None
    port = None
    for cand in [8799, 8800, 8801, 8802]:
        try:
            srv = http.server.ThreadingHTTPServer(('127.0.0.1', cand), H)
            port = cand
            break
        except OSError:
            continue
    if srv is None:
        print('ports busy'); sys.exit(1)
    url = 'http://127.0.0.1:%d/' % port
    print('Codex manager started: ' + url)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    srv.serve_forever()

if __name__ == '__main__':
    main()
