"""Self-contained, file:// compatible review UI. Drafts never approve source records."""
import json
from prepare_gx010021_media import ROOT, OUT

TEMPLATE = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GX010021 · 第一阶段事实核验</title>
<style>
:root{color-scheme:light;--ink:#142e36;--muted:#50666d;--line:#ccd8da;--accent:#0d625e}*{box-sizing:border-box}body{margin:0;background:#f2f6f5;color:var(--ink);font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif}header{background:#123b41;color:white;padding:22px 3vw}h1{font-size:25px;margin:0 0 8px}h2{font-size:19px;margin:8px 0}h3{font-size:16px}p{margin:8px 0}.badge{display:inline-block;background:#fff0cc;color:#644800;padding:2px 10px;border-radius:20px;font-size:12px;font-weight:700}.layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:20px;padding:20px 3vw}aside{align-self:start;position:sticky;top:10px;max-height:95vh;overflow:auto}main{min-width:0}.panel{background:white;border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:16px}.players{display:grid;grid-template-columns:1fr 1fr;gap:16px}video{width:100%;background:#101b20;border-radius:6px;max-height:350px}button,select,input,textarea{font:inherit}button{cursor:pointer;border:1px solid #a9bec0;background:white;color:var(--accent);border-radius:5px;padding:6px 10px;margin:3px}button:hover{background:#e7f4ef}button:focus-visible,a:focus-visible{outline:3px solid #da9b26}.task{display:block;text-align:left;width:97%;padding:9px}.task.active{background:#d7ede6;border-color:#0d625e}small,.muted{color:var(--muted)}.row{padding:12px 0;border-bottom:1px solid var(--line)}.row:last-child{border:0}.tag{color:var(--accent);font-weight:650}.evidence{border-left:3px solid #4e827c;padding:5px 12px;margin:9px 0}.annotation{border-left-color:#c99b3b;background:#fffaf0}.frames{display:flex;gap:8px;overflow:auto}.frames img{width:190px;max-width:100%;border-radius:4px}textarea{width:100%;height:110px;border:1px solid #a9bec0;border-radius:5px;padding:8px}label{display:block}details{margin-top:12px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}a{color:#0d625e}#clock{font-variant-numeric:tabular-nums}#annotations{max-height:400px;overflow:auto}#search{width:100%;padding:7px;border:1px solid #a9bec0;border-radius:5px}#draftStatus{min-height:25px}@media(max-width:1050px){.layout{grid-template-columns:220px minmax(0,1fr)}.players{grid-template-columns:1fr}}@media(max-width:720px){.layout{display:block}aside{position:static;max-height:300px}.frames img{width:140px}}
</style>
<header><h1>GX010021 · 视频事实核验工作台</h1><span class="badge">CANDIDATE / PENDING · 无 Gold</span> <span>696.930秒 · 无音轨 · 人工审定前全部禁用</span></header>
<div class="layout"><aside class="panel"><h2>候选任务</h2><label>Track 筛选 <select id="track"><option>全部</option><option>T1</option><option>T2</option><option>T3</option></select></label><label>检索题面<input id="search" placeholder="鸡蛋、烤模、规则…"></label><div id="tasks"></div><p><a href="review_data.json">完整候选与来源 JSON</a><br><a href="timeline.md">时间线与人工片段清单</a><br><a href="tasks.md">任务分析文档</a><br><a href="README.md">方法、复现与限制</a></p></aside>
<main><section class="panel"><h2>核验边界</h2><p>视觉观察是 AI 对本地解码帧的候选描述；原始文字标注单独显示。无音轨，无法核验真实语音、许可和口头承诺。状态、规则效力、充分证据与历史必要性均需人工审定。</p><details><summary>取样范围与时间语义</summary><p id="method"></p><p id="limits"></p><p>候选片段是已检查画面的证据包络，时间边界并非精确动作起止。播放器是离线审核工具，可浏览未来；正式任务引用另做查询时刻校验。不要将本页或完整转写用作在线 Agent 输入。</p></details></section>
<section class="players"><div class="panel"><h2>原视频 <small id="clock">0.000s</small></h2><video id="original" controls preload="metadata" src="../../../videos/GX010021.MP4"></video><label>跳转到秒 <input id="seek" type="number" min="0" max="696.929567" step="0.1" value="0"><button id="go">跳转</button><button id="query">到查询时刻</button></label><label>播放速度 <select id="speed"><option value="0.5">0.5×</option><option value="1" selected>1×</option><option value="1.5">1.5×</option><option value="2">2×</option></select></label></div><div class="panel"><h2>关键片段 <small id="clipLabel">请选择一条证据</small></h2><video id="clip" controls preload="metadata"></video><p class="muted">640px审核代理片段，零点相对该片段；原视频定位始终使用绝对秒。</p><p id="mediaError" role="status"></p></div></section>
<section class="panel" id="taskDetail"></section>
<section class="panel"><h2>审核草稿</h2><p>这里仅保存待审意见，不批准实体、不写入数据包、不生成 Gold。导出后交由真实审核者独立复核。</p><label>审核者署名（草稿）<input id="reviewer" placeholder="填写实际审核者"></label><label>事实观察、边界调整、替代证据与分歧<textarea id="note" placeholder="记录观看区间与理由；不能仅写同意"></textarea></label><button id="save">保存本机草稿</button><button id="export">导出全部待审草稿 JSON</button><p id="draftStatus" role="status"></p></section>
<section class="panel"><h2>真实视频事件与状态候选时间线</h2><p class="muted">点击可播放代理片段及跳转原视频。所有动作/状态保持候选；UNKNOWN不代表人工认定不可观察。</p><div id="timeline"></div></section>
<section class="panel"><h2>全部55条原始文字标注</h2><p class="muted">原样引用，标签和点时间来自 annotations.json；均非已验证语音。标注点不是动作完成时间。</p><div id="annotations"></div></section>
<section class="panel"><h2>E1–E6统一定义</h2><div id="experiments"></div><p>旧实验计划已备份并保留原文件；新定义为独立版本，全部禁用。</p></section>
</main></div>
<script id="data" type="application/json">__DATA__</script>
<script>
'use strict';
const D=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);
const E=new Map(D.evidence.map(x=>[x.id,x])), T=new Map(D.timeline.map(x=>[x.evidence_ref,x]));
let selected=D.tasks[0], drafts={}; const storageKey='GX010021_phase1_20261027_PENDING_drafts';
try{drafts=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(e){$('draftStatus').textContent='本地存储不可用，仍可导出本次草稿。'}
function el(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e}
function button(text,fn){const b=el('button',text);b.addEventListener('click',fn);return b}
function seek(t){$('original').currentTime=t;$('seek').value=t}
function play(ref){const e=E.get(ref);if(!e)return;seek(e.interval.start);let key=ref.split(':').pop();$('clipLabel').textContent=`${e.interval.start.toFixed(3)}–${e.interval.end.toFixed(3)}s 原视频`;
if(e.source_id==='src:video'){$('clip').src='clips/'+key+'.mp4';$('clip').load();$('clip').play().catch(()=>{});}else{$('clipLabel').textContent='文字点锚；请在原视频复核'} }
function evidence(ref){const e=E.get(ref), box=el('div',undefined,'evidence'+(e.source_id==='src:annotation'?' annotation':''));
box.append(el('strong',`${e.source_id==='src:video'?'视觉候选':'原始文字 / 真实语音未核验'} · ${e.interval.start}–${e.interval.end}s`));
box.append(el('p',e.quote===null?(T.get(ref)?.observation||'查询前当前窗口；供替代证据检查'):e.quote));
box.append(el('small',`${e.source_label} | ${e.source_pointer}`),document.createElement('br'),button('定位 / 播放',()=>play(ref)));
if(T.has(ref)){const r=T.get(ref);box.append(el('p','限制：'+r.uncertainty));const fs=el('div',undefined,'frames');const frames=r.frames;const indices=[0,Math.floor(frames.length/2),frames.length-1];for(const i of [...new Set(indices)]){if(!frames[i])continue;const f=frames[i],a=el('a');a.href=f.path;a.target='_blank';const img=el('img');img.src=f.path;img.loading='lazy';img.alt=`解码帧 PTS ${f.pts_seconds}s`;a.append(img,el('small',`${f.pts_seconds}s`));fs.append(a)}box.append(fs)}return box}
function taskList(){const list=$('tasks');list.replaceChildren();for(const t of D.tasks){if($('track').value!=='全部'&&$('track').value!==t.track)continue;if(!t.question.includes($('search').value))continue;const b=button(`${t.track} · ${t.query_time}s\n${t.question}`,()=>select(t));b.className='task'+(t===selected?' active':'');b.dataset.task=t.id;list.append(b)}}
function select(t){selected=t;taskList();const box=$('taskDetail');box.replaceChildren(el('span','CANDIDATE / PENDING','badge'),el('h2',t.question),el('p',`查询 ${t.query_time}s；当前窗口 [${t.window_start}, ${t.query_time}]；历史距离 ${t.history_gap_seconds===null?'UNKNOWN':t.history_gap_seconds+'s'}（查询减历史证据最晚结束，仅描述统计）`));
for(const [title,value] of [['候选答案（非Gold）',t.candidate_answer],['替代证据检查',t.alternative_evidence_check],['历史必要性分析 · PENDING',t.history_necessity_analysis],['独立遮蔽审核建议',t.counterfactual_review]])box.append(el('h3',title),el('p',value));
for(const [title,refs] of [['历史证据',t.history_evidence],['当前证据',t.current_evidence],['原始文字（与视觉分层）',t.annotation_evidence]]){box.append(el('h3',title));if(!refs.length)box.append(el('p','无 / UNKNOWN'));for(const ref of refs)box.append(evidence(ref))}
const details=el('details');details.append(el('summary','任务完整记录与待确认字段'),el('pre',JSON.stringify(t,null,2)));box.append(details);$('note').value=drafts[t.id]?.notes||'';$('reviewer').value=drafts[t.id]?.reviewer||'';$('seek').value=t.query_time;}
$('method').textContent=D.method;$('limits').textContent=D.coverage_limits;
$('track').addEventListener('change',taskList);$('search').addEventListener('input',taskList);
$('go').onclick=()=>{const t=Number($('seek').value);if(Number.isFinite(t)&&t>=0&&t<=D.duration)seek(t)};
$('query').onclick=()=>seek(selected.query_time);$('speed').onchange=()=>{$('original').playbackRate=Number($('speed').value);$('clip').playbackRate=Number($('speed').value)};
$('original').addEventListener('timeupdate',()=>{$('clock').textContent=$('original').currentTime.toFixed(3)+'s'});
for(const id of ['original','clip'])$(id).addEventListener('error',()=>{$('mediaError').textContent='视频加载失败：请保留本页与项目目录的相对位置，或从项目根目录运行 python -m http.server 8000 后打开本页。'});
function save(){drafts[selected.id]={task_ref:selected.id,maturity:'CANDIDATE',review:{status:'PENDING',reviewer:null,reviewed_at:null,notes:'Local draft only; no adjudication.'},reviewer:$('reviewer').value,notes:$('note').value,draft_saved_at:new Date().toISOString()};try{localStorage.setItem(storageKey,JSON.stringify(drafts));$('draftStatus').textContent='已保存本机待审草稿；源文件与Gold未修改。'}catch(e){$('draftStatus').textContent='本机存储受限；草稿暂存内存，请导出。'}}
$('save').onclick=save;$('export').onclick=()=>{save();const blob=new Blob([JSON.stringify({episode:D.episode,maturity:'CANDIDATE',review:{status:'PENDING'},drafts},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=el('a');a.href=url;a.download='GX010021_PENDING_review_drafts.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
for(const r of D.timeline){const row=el('div',undefined,'row');row.append(el('strong',`${r.start}–${r.end}s · ${r.key}`),el('p',r.observation),el('p',`状态：${r.subject}.${r.property} = ${r.value===null?'UNKNOWN':r.value} [${r.basis}]`),el('small',r.uncertainty),document.createElement('br'),button('审看片段',()=>play(r.evidence_ref)));$('timeline').append(row)}
for(const e of D.evidence.filter(x=>x.source_id==='src:annotation'))$('annotations').append(evidence(e.id));
for(const [id,name] of Object.entries(D.experiment_mapping.definitions))$('experiments').append(el('p',id+' · '+name));
select(selected);
</script></html>'''

def main():
    data=json.loads((OUT/'review_data.json').read_text(encoding='utf-8'))
    (OUT/'index.html').write_text(TEMPLATE.replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/')),encoding='utf-8')
    timeline=['# GX010021 视觉事件与状态候选时间线','', '全部 CANDIDATE / PENDING；非 Gold。无音轨。时间为已检查证据包络，精确动作起止 UNKNOWN。','',data['method'],'',data['coverage_limits'],'','| 证据区间（秒） | 实际画面候选 | 状态候选 | 人工确认重点 |','|---|---|---|---|']
    for r in data['timeline']:
        value='UNKNOWN' if r['value'] is None else r['value']
        timeline.append(f"| [{r['start']}–{r['end']}](clips/{r['key']}.mp4) | {r['observation']} | {r['subject']}.{r['property']} = {value} | {r['uncertainty']} |")
    timeline += ['', '## 人工关键片段队列', '', '优先：60–90秒鸡蛋数量与放回；390–432秒两次取出时固体状态；556–581秒烤模处理与覆盖；598–604秒追加白粉；632–642秒实际倒入起点；686–694秒入烤箱。', '', '8–16秒烤箱温度、94–166秒量杯刻度与材料身份、472–530/604–630秒平滑度标准、所有55条真实语音均保持 UNKNOWN/PENDING。其余逐段事项已列在表格与 review_data.json.human_queue。', '', '每项需真实审核者记录观看范围、确认或拒绝的具体命题、精确边界和理由；关键分歧独立复核。当前没有人工批准记录。']
    (OUT/'timeline.md').write_text('\n'.join(timeline)+'\n',encoding='utf-8')
    tasks=['# T1–T3 候选任务与历史必要性分析','','全部 CANDIDATE / PENDING，enabled=false，earliest_answerable_time=null。候选答案只在此侧车/审核JSON中，gold.jsonl仍为空。','', '当前窗口30秒只是审核提案；10/30/60秒敏感性检查尚未执行。历史距离为查询减拟议历史证据最晚结束，不是已确认的历史依赖距离。充分/最小集合与历史必要性均PENDING。']
    for t in data['tasks']:
        tasks += ['', '## '+t['id'].split(':')[-1], '',f"查询：{t['query_time']}秒；题面：{t['question']}", '',f"历史：{', '.join(t['history_evidence']) or '无/UNKNOWN'}",'',f"当前：{', '.join(t['current_evidence'])}",'',f"文字：{', '.join(t['annotation_evidence']) or '无'}",'', '候选答案：'+t['candidate_answer'],'','替代证据：'+t['alternative_evidence_check'],'','历史必要性：'+t['history_necessity_analysis'],'','人工遮蔽复核：'+t['counterfactual_review']]
    (OUT/'tasks.md').write_text('\n'.join(tasks)+'\n',encoding='utf-8')
    print('Rendered index.html, timeline.md and tasks.md')

if __name__=='__main__': main()
