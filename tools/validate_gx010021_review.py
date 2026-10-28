"""Additive validation for phase-one sidecars, causal cuts and preserved assets."""
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmark.validate import load_bundle, validate_bundle, verify_assets, digest
from prepare_gx010021_media import ROOT, OUT, write_json

DATA=ROOT/'datasets/ego_mc/GX010021_video_phase1_20261027'

def validate_review(review,bundle):
    errors=[]
    ev={e['id']:e for e in bundle['evidence']}
    records={r['id']:r for r in bundle['records']}
    def pending(x):
        return x.get('maturity')=='CANDIDATE' and x.get('review',{}).get('status')=='PENDING' and not x.get('review',{}).get('reviewer') and not x.get('review',{}).get('reviewed_at')
    if not pending(review): errors.append('REVIEW_GATE sidecar must remain pending')
    if review.get('audio_present') is not False: errors.append('AUDIO_GATE source contains no audio stream')
    for row in review.get('timeline',[]):
        if not pending(row): errors.append('REVIEW_GATE timeline '+row.get('key','?'))
        source=ev.get(row.get('evidence_ref'))
        if not source or source['source_id']!='src:video': errors.append('VISUAL_SOURCE timeline needs video evidence'); continue
        if source['interval']!={'start':row['start'],'end':row['end']}: errors.append('INTERVAL timeline/evidence mismatch')
        if source['source_pointer']!=f"videos/GX010021.MP4#t={row['start']},{row['end']}": errors.append('VIDEO_POINTER mismatch')
        if row['value'] is None and row['basis']!='unknown': errors.append('UNKNOWN_BASIS mismatch')
        if row.get('exact_action_start') is not None or row.get('exact_action_end') is not None: errors.append('BOUNDARY_GATE exact boundaries not human verified')
        if not row.get('frames'): errors.append('COVERAGE no inspected decoded frames')
        for f in row.get('frames',[]):
            if not row['start']<=f['pts_seconds']<=row['end']: errors.append('FRAME_TIME outside evidence envelope')
    required=['query_time','history_evidence','current_evidence','annotation_evidence','candidate_answer',
              'alternative_evidence_check','history_necessity_analysis','history_necessity','counterfactual_review']
    for t in review.get('tasks',[]):
        if not all(k in t for k in required): errors.append('TASK_FIELDS missing analysis fields'); continue
        if not pending(t) or t.get('enabled') is not False or t['history_necessity']!='PENDING': errors.append('TASK_GATE unreviewed sidecar task')
        native=records.get(t['id'])
        if not native or native['type']!='Task': errors.append('TASK_REF unresolved native task'); continue
        if t['query_time']!=native['payload']['query_time']: errors.append('TASK_TIME sidecar/native mismatch')
        refs=t['history_evidence']+t['current_evidence']+t['annotation_evidence']
        if set(refs)!=set(native['evidence_refs']): errors.append('TASK_EVIDENCE sidecar/native mismatch')
        for ref in refs:
            e=ev.get(ref)
            if not e: errors.append('REFERENCE missing task evidence'); continue
            if e['interval']['end']>t['query_time']: errors.append('FUTURE_LEAK sidecar task evidence')
            if ref in t['annotation_evidence'] and e['source_id']!='src:annotation': errors.append('SOURCE_LAYER annotation mismatch')
            if ref in t['history_evidence']+t['current_evidence'] and e['source_id']!='src:video': errors.append('SOURCE_LAYER visual mismatch')
        if not t['current_evidence']: errors.append('CURRENT_WINDOW missing')
        for k in ['candidate_answer','alternative_evidence_check','history_necessity_analysis','counterfactual_review']:
            if not isinstance(t[k],str) or not t[k].strip(): errors.append('TASK_ANALYSIS empty '+k)
    if any(r['type']=='Gold' for r in bundle['records']): errors.append('GOLD_GATE phase one must remain empty')
    return errors

def main():
    review=json.loads((OUT/'review_data.json').read_text(encoding='utf-8'))
    bundle=load_bundle(DATA)
    report=validate_bundle(bundle)
    report['errors']+=validate_review(review,bundle)
    html=(OUT/'index.html').read_text(encoding='utf-8')
    embedded=re.search(r'<script id="data" type="application/json">(.*?)</script>',html,re.S)
    if not embedded or json.loads(embedded.group(1))!=review: report['errors'].append('HTML_DATA stale embedded review')
    before=json.loads((OUT/'preservation_before.json').read_text(encoding='utf-8'))
    protected=[r for r in before if r['path'] not in ['README.md','experiments/README.md']]
    changed=[r['path'] for r in protected if not (ROOT/r['path']).is_file() or digest(ROOT/r['path'])!=r['sha256']]
    report['preserved_existing_files']={'checked':len(protected),'changed':changed}
    report['errors'] += ['PRESERVATION '+p for p in changed]
    for r in before:
        if r['path'].startswith('experiments/'):
            backup=OUT/'experiment_backup'/Path(r['path']).relative_to('experiments')
            if not backup.is_file() or digest(backup)!=r['sha256']: report['errors'].append('EXPERIMENT_BACKUP '+r['path'])
    assets=verify_assets(ROOT/'results/preparation/original_assets.json')
    report['original_assets']=assets; report['errors']+=assets['errors']
    # Original candidate bytes remain an exact prefix in the additive version, except Episode provenance.
    for p in (ROOT/'datasets/ego_mc/GX010021').glob('*'):
        if p.name=='episode.json': continue
        if not (DATA/p.name).read_bytes().startswith(p.read_bytes()): report['errors'].append('LEGACY_PREFIX '+p.name)
    clip_manifest=json.loads((OUT/'clip_manifest.json').read_text(encoding='utf-8'))
    for c in clip_manifest:
        if digest(OUT/c['path'])!=c['sha256']: report['errors'].append('CLIP_HASH '+c['key'])
        length=c['source_interval']['end']-c['source_interval']['start']
        if abs(length-c['duration'])>0.1: report['errors'].append('CLIP_DURATION '+c['key'])
        if c['audio_streams']: report['errors'].append('CLIP_AUDIO unexpected')
    fi=json.loads((OUT/'frame_index.json').read_text(encoding='utf-8'))
    for f in fi:
        if digest(OUT/f['path'])!=f['sha256']: report['errors'].append('FRAME_HASH '+f['path'])
    keyindex=json.loads((OUT/'keyframe_image_index.json').read_text(encoding='utf-8'))
    keymeta=json.loads((OUT/'keyframes.json').read_text(encoding='utf-8'))['frames']
    if len(keyindex)!=len(keymeta): report['errors'].append('KEYFRAME_COUNT mismatch')
    for f,meta in zip(keyindex,keymeta):
        if f['pts_seconds']!=float(meta['best_effort_timestamp_time']) or digest(OUT/f['path'])!=f['sha256']:
            report['errors'].append('KEYFRAME_HASH_PTS '+f['path'])
    if len(fi)!=349 or any(b['pts_seconds']<=a['pts_seconds'] for a,b in zip(fi,fi[1:])): report['errors'].append('FRAME_PTS coverage/order')
    media=json.loads((OUT/'ffprobe.json').read_text(encoding='utf-8'))
    if any(s['codec_type']=='audio' for s in media['streams']): report['errors'].append('AUDIO_SOURCE mismatch')
    for i in range(1,7):
        p=json.loads((ROOT/f'experiments/phase1_20261027/E{i}/plan.json').read_text(encoding='utf-8'))
        if p['enabled'] or p['executed'] or p['maturity']!='CANDIDATE' or p['review']['status']!='PENDING': report['errors'].append('EXPERIMENT_GATE '+p['id'])
    report['counts']={'visual_event_state_pairs':len(review['timeline']),'new_tasks':len(review['tasks']),
                      'new_dependencies':len(review['dependencies']),'clips':len(clip_manifest),'decoded_frames':len(fi),
                      'encoded_keyframe_images':len(keyindex),'gold_bytes':(DATA/'gold.jsonl').stat().st_size}
    report['status']='FAIL' if report['errors'] else 'PASS'
    write_json(OUT/'review_validation.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return bool(report['errors'])

if __name__=='__main__': sys.exit(main())
