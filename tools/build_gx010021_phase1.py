"""Package visually inspected CANDIDATE notes without altering the original bundle."""
import copy
import json
from pathlib import Path
import shutil
import subprocess

from prepare_gx010021_media import ROOT, OUT, sha, write_json

DATA = ROOT / 'datasets/ego_mc/GX010021_video_phase1_20261027'
PREFIX = 'ego_mc:GX010021:'
BASE = ROOT / 'datasets/ego_mc/GX010021'

def main():
    if DATA.exists() or (OUT / 'review_data.json').exists():
        raise FileExistsError('Refusing to overwrite a previously packaged review version')
    shutil.copytree(BASE, DATA)
    notes = json.loads((ROOT / 'tools/gx010021_visual_notes.json').read_text(encoding='utf-8'))
    pending = notes['review']
    rows = notes['timeline']
    evidence = []
    records = {k: [] for k in ['events', 'states', 'dependencies', 'tasks']}
    def ev_id(key): return PREFIX + 'video_evidence:' + key
    def rid(kind,key): return PREFIX + 'visual_' + kind + ':' + key
    def ev(key,a,b,label='AI_VISUAL_CANDIDATE'):
        r = {'id':ev_id(key), 'episode_id':PREFIX[:-1], 'source_id':'src:video',
             'interval':{'start':a,'end':b}, 'available_at':None, 'visibility':'PRIVATE',
             'source_pointer':f'videos/GX010021.MP4#t={a},{b}', 'quote':None,
             'source_label':label,'maturity':'CANDIDATE','review':copy.deepcopy(pending)}
        evidence.append(r)
        return r['id']
    def record(kind,key,a,b,refs,payload,derived=()):
        return {'schema_version':'0.1.0','id':rid(kind.lower(),key),'episode_id':PREFIX[:-1],
                'type':kind,'interval':{'start':a,'end':b},'known_at':b,'visibility':'PRIVATE',
                'maturity':'CANDIDATE','review':copy.deepcopy(pending),'evidence_refs':list(refs),
                'derived_from':list(derived),'provenance':{'method':'text_candidate',
                'notes':'AI视觉观察/候选推理，非人工审定。Schema 0.1.0未设模型来源枚举，沿用text_candidate并在此明确：动作与状态来自本地解码画面，非原发言转成动作。详见review_data.json的方法、取样PTS及不确定性。'},'payload':payload}
    frames = json.loads((OUT/'frame_index.json').read_text(encoding='utf-8'))
    for row in rows:
        k,a,b = row['key'],row['start'],row['end']
        ref = ev(k,a,b)
        event = record('Event',k,a,b,[ref],{'kind':'observed_action','text':row['observation'],'source_label':'AI_VISUAL_CANDIDATE'})
        state = record('State',k,b,b,[ref],{x:row[x] for x in ['subject','property','value','basis']},[event['id']])
        records['events'].append(event); records['states'].append(state)
        row.update({'id':event['id'],'state_ref':state['id'],'evidence_ref':ref,'maturity':'CANDIDATE',
                    'review':copy.deepcopy(pending),'source_layer':'VISUAL_OBSERVATION_AI_CANDIDATE',
                    'interval_semantics':'inspected_evidence_envelope_not_exact_action_boundary',
                    'exact_action_start':None,'exact_action_end':None,
                    'frames':[f for f in frames if a<=f['pts_seconds']<=b],
                    'clip':f'clips/{k}.mp4'})
    def state(k): return rid('state',k)
    def rule(i): return PREFIX+f'rule:{i:03d}'
    def ann(i): return PREFIX+f'evidence:{i:03d}'
    dep_specs = [
        ('eggs_before_whisk',200,state('return_intact_egg'),rule(17),['return_intact_egg'],'candidate_precondition','两枚鸡蛋已打入可作为搅拌前置候选；配方要求只由原始文字提供，必要性/实际适用性PENDING。'),
        ('tray_before_pour',630.612,state('oil_pour_tilt'),rule(51),['oil_pour_tilt'],'candidate_precondition','画面可见液体处理烤模；处理是否构成必要前置、覆盖是否足够及规范是否允许均PENDING。'),
        ('egg_history',525,state('return_intact_egg'),state('crack_second'),['crack_second','return_intact_egg'],'historical_context','两次打开蛋壳与第三枚完整蛋放回的历史可支持后续原料数量回忆；混合物对象连续性、替代证据及历史必要性PENDING。'),
        ('butter_history',525,state('butter_second_check'),state('butter_first_check'),['butter_first_check','butter_second_check'],'historical_context','两轮微波取出时的黄色块状物用于历史状态回溯；不从后续面糊外观反推早期完全融化。'),
        ('tray_history',630.612,state('oil_pour_tilt'),state('tray_inspection'),['tray_inspection','oil_pour_tilt'],'historical_context','历史可见倒液体/倾斜，与当前烤模残留光泽作替代检查；历史必要性未确认。')]
    dep_ids={}
    for k,q,f,t,keys,rel,reason in dep_specs:
        refs=[ev_id(x) for x in keys]
        d=record('Dependency',k,q,q,refs,{'relation':rel,'from_ref':f,'to_ref':t,'rationale':reason})
        records['dependencies'].append(d); dep_ids[k]=d['id']
    specs = [
        ('T1_oven', 'T1',16,'此时是否已实际达到350°F？',[],['oven_controls'],[state('oven_controls')],[], 'UNKNOWN；只看到按键，未可靠读出实测温度。','当前显示屏可能提供替代证据，需原分辨率连续复核；设定值仍不等于实测值。','当前窗口即可检查按键与显示，历史未表现必要；温度可回答性本身PENDING。'),
        ('T1_eggs','T1',90,'截至90秒，透明方盒里有几枚可见蛋黄？',['crack_first','crack_second'],['return_intact_egg'],[state('return_intact_egg')],[], '候选2；不把第三枚取出当作第三枚已打入。','78–90秒盒内两个蛋黄本身可能充分；不能宣称必须依赖首次打蛋历史。','弱历史/当前可见对照候选；历史必要性仍PENDING。'),
        ('T1_butter','T1',432,'第二次从微波炉取出时，容器中是否仍有可见黄色块状物？',['butter_first_check'],['butter_second_check'],[state('butter_second_check')],[], '候选有；完全融化不可确认。','426–432秒取出近景可直接回答；431.658秒Success不作事实支持。','当前近景可能足够，历史不是强必要候选。'),
        ('T2_eggs','T2',200,'开始搅拌前，“加入两枚鸡蛋”候选前置是否满足？',['crack_first','crack_second','return_intact_egg'],[],[dep_ids['eggs_before_whisk'],state('return_intact_egg')],[8,17], '事实子项候选已加入两枚；规范充分性与完整任务答案UNKNOWN。','170–200秒混合前盒内蛋黄仍可见，可能直接计数；原始指令文本也可给数量捷径，但不能证明动作完成。','当前窗可能足够计数；不作为已确认长程任务。'),
        ('T2_tray','T2',630.612,'倒面糊之前，烤模准备这一候选前置是否已实际满足？',['oil_pour_tilt'],[],[dep_ids['tray_before_pour'],state('oil_pour_tilt')],[38,40,42,51], '事实子项候选已倒入淡黄色液体并倾斜；是否符合必要覆盖/许可标准UNKNOWN。','600.612–630.612秒烤模在旁可见，残留光泽可能给出捷径；逐帧评估是否充分，不能只看曾倒油。','历史提供操作来源；规范必要性与当前替代充分性均PENDING。'),
        ('T3_eggs_history','T3',525,'回顾当前混合物制作过程，最初实际打入了几枚鸡蛋？是否有完整蛋未加入，如何处理？',['crack_first','crack_second','return_intact_egg'],[],[dep_ids['egg_history'],state('return_intact_egg')],[], '候选打入2枚，第三枚完整蛋放回蛋盒；对象连续性待审。','495–525秒为搅拌近景，无法直接数原始鸡蛋；检查台面蛋壳、其他早期视角、题面先验及默认配方猜测。','较强跨窗口历史候选：原始数量/放回事件在当前画面不可直接重建；须做独立遮蔽审核，未运行模型或统计消融。'),
        ('T3_butter_history','T3',525,'第二次取出微波炉容器时，其中是否仍有黄色块状物？',['butter_first_check','butter_second_check'],[],[dep_ids['butter_history'],state('butter_second_check')],[], '候选有；物理融化程度/温度UNKNOWN。','当前495–525秒面糊外观无法确定426–432秒状态；首次取出可提示但不能替代第二次近景，Success文本可能诱发相反捷径。','跨窗口回溯候选，必须确认“第二次”对象与时间定位；历史必要性PENDING。'),
        ('T3_tray_history','T3',630.612,'在当前倒入前，操作者先前用什么可见方式处理了这个烤模？',['oil_pour_tilt'],[],[dep_ids['tray_history'],state('oil_pour_tilt')],[], '候选从透明瓶倒淡黄色液体并反复倾斜；材料为食用油是待审身份推断。','当前窗仍见烤模、瓶子与内表面光泽，可猜材料；该捷径未排除，不宣称历史必要。','约50秒以上的操作回忆候选，但当前残留状态可能足够，优先做人工遮蔽对照。'),
        ('T3_rule_chain','T3',556.368,'截至查询时刻，原始标注声称允许什么材料处理烤模，能否确认视频中实际许可链？',[],[],[rule(38),rule(40),rule(42)],[38,39,40,41,42], '原始文字候选为油；视频实际许可链UNKNOWN（无音轨）。','单条556.368秒“Yes, you can use oil.”已可能回答文本题；完整历史未必必要；画面拿瓶不证明得到许可。','保留为不可核验/语言捷径对照，不能升为视频规则推理Gold。')
    ]
    task_reviews=[]
    for k,track,q,question,hist,cur,targets,ais,answer,alt,necessity in specs:
        current_start=max(0,q-30)
        current_ref=ev(k+'_current',current_start,q,'AI_VISUAL_WINDOW_CANDIDATE')
        h=[ev_id(x) for x in hist]; c=list(dict.fromkeys([ev_id(x) for x in cur]+[current_ref]))
        ar=[ann(i) for i in ais]
        allrefs=list(dict.fromkeys(h+c+ar))
        payload={'track':track,'question':question,'query_time':q,'earliest_answerable_time':None,
                 'required_evidence_sets':[allrefs], 'target_refs':targets,
                 'answer_type':{'T1':'state_or_unknown','T2':'satisfied_unsatisfied_unknown','T3':'text_or_unknown'}[track],
                 'history_necessity':'PENDING','enabled':False}
        task=record('Task',k,q,q,allrefs,payload)
        records['tasks'].append(task)
        last_history=max((e['interval']['end'] for e in evidence if e['id'] in h),default=None)
        task_reviews.append({'id':task['id'],'track':track,'question':question,'query_time':q,
            'maturity':'CANDIDATE','review':copy.deepcopy(pending),'history_evidence':h,'current_evidence':c,
            'annotation_evidence':ar,'candidate_answer':answer,'alternative_evidence_check':alt,
            'history_necessity_analysis':necessity,'history_necessity':'PENDING',
            'sufficiency':'PENDING','minimality':'PENDING','rule_validity':'PENDING' if ais else 'UNKNOWN',
            'current_window_seconds':30,'window_start':current_start,
            'history_gap_seconds':None if last_history is None else round(q-last_history,3),
            'history_distance_definition':'query minus latest end among proposed historical evidence; descriptive only',
            'sensitivity_windows_seconds':[10,30,60],
            'counterfactual_review':'先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。',
            'unverified_fields':['earliest_answerable_time','exact_action_boundaries','sufficient_minimal_evidence','human_history_necessity'],
            'enabled':False})
    for name,items in records.items():
        with (DATA/(name+'.jsonl')).open('a',encoding='utf-8',newline='\n') as f:
            for item in items: f.write(json.dumps(item,ensure_ascii=False)+'\n')
    with (DATA/'evidence.jsonl').open('a',encoding='utf-8',newline='\n') as f:
        for item in evidence: f.write(json.dumps(item,ensure_ascii=False)+'\n')
    ep=json.loads((DATA/'episode.json').read_text(encoding='utf-8'))
    ep['provenance'] += ' Phase-one version adds AI visual candidates from inspected local frames; no human approval, audio absent. Original bundle retained byte-for-byte.'
    write_json(DATA/'episode.json',ep)
    # Back up research materials and publish a separately versioned definition set.
    backup=OUT/'experiment_backup'; backup.mkdir()
    for p in sorted((ROOT/'experiments').rglob('*')):
        if p.is_file():
            dest=backup/p.relative_to(ROOT/'experiments'); dest.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,dest)
    shutil.copyfile(ROOT/'configs/preparation.json',backup/'preparation_config.json')
    definitions=[('连续状态维护',['T1'],'在连续检查点维护对象状态与转移，未知状态不能靠Success回填。',['checkpoint_state_accuracy','transition_consistency','update_delay']),
        ('历史必要性',['T1','T2','T3'],'固定当前窗口，比较移除/保留必要历史；独立人工确认充分性并排除替代证据。',['paired_answer_change','reviewed_history_necessity']),
        ('历史距离',['T3'],'在已确认必要历史子集上按查询到证据的距离分层，控制任务难度与窗口预算。',['accuracy_by_history_distance','evidence_retrieval_by_distance']),
        ('规则推理',['T2','T3'],'区分规范与事实，审核规则条件、范围和版本后再评估。',['constraint_judgment','rule_version_selection']),
        ('记忆消融',['T1','T2','T3'],'固定模型与输入预算，对比窗口、摘要、检索和显式状态记忆。',['task_accuracy','state_consistency','memory_cost']),
        ('实时性',['T1','T2','T3'],'后续因果流中测量更新延迟、吞吐和告警时效；不得把Feedback时间当错误起点。',['wall_clock_latency','real_time_factor','detectable_to_response_delay'])]
    newdir=ROOT/'experiments/phase1_20261027'; newdir.mkdir(exist_ok=False)
    old_to_new={'E1':['E2','E3','E5'],'E2':['E1','E5'],'E3':['E4'],'E4':['E2','E3','E4'],'E5':['E2','E5'],'E6':['E3','E5','E6']}
    for i,(title,tracks,question,metrics) in enumerate(definitions,1):
        p=newdir/f'E{i}'; p.mkdir()
        write_json(p/'plan.json',{'id':f'E{i}','title':title,'definition_version':'phase1_20261027','maturity':'CANDIDATE',
            'review':copy.deepcopy(pending),'status':'PENDING','enabled':False,'tracks':tracks,'question':question,'proposed_metrics':metrics,
            'prerequisites':['approved_gold','reviewed_sufficient_evidence','causal_visibility','fixed_budget','implemented_runner'],
            'calibration':{'windows':None,'distance_bins':None,'latency_thresholds':None},'executed':False})
    mapping={'maturity':'CANDIDATE','review':copy.deepcopy(pending),'canonical_version':'phase1_20261027',
             'definitions':{f'E{i}':d[0] for i,d in enumerate(definitions,1)},'legacy_to_canonical':old_to_new,
             'mapping_notes':'多对多概念映射，不表示旧实验已完成；旧E5可见性诊断作为E2/E5控制因素，旧E6跨来源扩展保留为未来工作，不在本阶段运行。E6新增统一实时性目标。',
             'legacy_backup':backup.relative_to(ROOT).as_posix(),'legacy_plans_unchanged':True}
    write_json(newdir/'mapping.json',mapping)
    write_json(ROOT/'configs/video_review_phase1.json',{'maturity':'CANDIDATE','review':copy.deepcopy(pending),
        'episode_dir':DATA.relative_to(ROOT).as_posix(),'experiment_definition_version':'phase1_20261027',
        'experiment_plans':[f'experiments/phase1_20261027/E{i}/plan.json' for i in range(1,7)],
        'run_evaluation':False,'run_models':False,'replay_implemented':False})
    # Extract playable review clips; every clip is a derived proxy, never a replacement for original MP4.
    clips=OUT/'clips'; clips.mkdir()
    commands=[]; media=[]
    spans=[(r['key'],r['start'],r['end']) for r in rows]
    spans += [(s['id'].split(':')[-1]+'_current',s['window_start'],s['query_time']) for s in task_reviews]
    for key,a,b in spans:
        dest=clips/(key+'.mp4')
        args=['ffmpeg','-v','error','-n','-ss',str(a),'-i',str(ROOT/'videos/GX010021.MP4'),'-t',str(b-a),'-map','0:v:0','-an','-vf','scale=640:-2','-c:v','libx264','-preset','veryfast','-crf','23','-movflags','+faststart',str(dest)]
        subprocess.run(args,check=True,capture_output=True); commands.append(args)
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(dest)],text=True))
        media.append({'key':key,'path':dest.relative_to(OUT).as_posix(),'source_interval':{'start':a,'end':b},
                      'source_sha256':sha(ROOT/'videos/GX010021.MP4'),'sha256':sha(dest),
                      'duration':float(probe['format']['duration']),'audio_streams':sum(s['codec_type']=='audio' for s in probe['streams']),
                      'maturity':'CANDIDATE','review':copy.deepcopy(pending)})
    write_json(OUT/'clip_commands.json',commands); write_json(OUT/'clip_manifest.json',media)
    # Repair detail-sheet creation so only numeric frame filenames can enter a sheet.
    from PIL import Image,ImageDraw
    detail=OUT/'detail'
    for name,a,b in [('eggs',60,90),('oil',554,582),('butter',426,434),('powder',598,604),('oven',686,694)]:
        files=sorted(detail.glob(name+'_[0-9][0-9][0-9].jpg'))
        for offset in range(0,len(files),12):
            canvas=Image.new('RGB',(1200,1000),'#101820'); draw=ImageDraw.Draw(canvas)
            for j,p in enumerate(files[offset:offset+12]):
                x,y=(j%3)*400,(j//3)*250
                canvas.paste(Image.open(p).resize((400,225)),(x,y+25))
                draw.text((x+5,y+5),f'{name} nominal ~{a+.5*(offset+j):.1f}s (2fps)',fill='white')
            canvas.save(detail/f'{name}_sheet{offset//12}.jpg')
    all_ev=[json.loads(x) for x in (DATA/'evidence.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
    review={'maturity':'CANDIDATE','review':pending,'episode':'GX010021','audio_present':False,
        'duration':ep['duration_seconds'],'method':notes['method'], 'schema_provenance_note':'provenance.method=text_candidate is retained to fit the unchanged 0.1.0 enum; source_label and notes distinguish AI visual candidates from original text annotations. No entry claims human review.',
        'objects':notes['objects'],'timeline':rows,'tasks':task_reviews,'evidence':all_ev,
        'dependencies':records['dependencies'],'experiment_mapping':mapping,
        'candidate_bundle':DATA.relative_to(ROOT).as_posix(),
        'coverage_limits':'约2秒取样覆盖全片，重点5段加密到2fps；非连续逐帧穷尽。区间为已检查证据包络，精确起止UNKNOWN。取样间短动作、遮挡、画面外行为与所有实际语音均未核验。',
        'human_queue':[{'key':r['key'],'interval':{'start':r['start'],'end':r['end']},'question':r['uncertainty'],'maturity':'CANDIDATE','review':copy.deepcopy(pending)} for r in rows]}
    write_json(OUT/'review_data.json',review)
    print(f'Packaged {len(rows)} visual event/state pairs, {len(task_reviews)} tasks, {len(media)} clips.')

if __name__=='__main__': main()
