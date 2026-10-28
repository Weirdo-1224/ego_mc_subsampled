"""Read-only source extraction for the phase-one visual review (no model API)."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/video_review/GX010021_phase1_20261027'

def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    from PIL import Image, ImageDraw
    OUT.mkdir(parents=True, exist_ok=False)
    paths = [ROOT / 'benchmark/schema.json', *sorted((ROOT / 'datasets/ego_mc/GX010021').glob('*')),
             *sorted((ROOT / 'experiments').rglob('*')),
             ROOT / 'README.md', ROOT / 'results/preparation/human_review.md']
    paths += [ROOT / x['path'] for x in json.loads((ROOT / 'results/preparation/original_assets.json').read_text(encoding='utf-8'))['files']]
    # Source manifests from the existing bundle include all inputs used here.
    paths += [ROOT / x['path'] for x in json.loads((ROOT / 'datasets/ego_mc/GX010021/sources.json').read_text(encoding='utf-8'))]
    write_json(OUT / 'preservation_before.json', [{'path': p.relative_to(ROOT).as_posix(), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(set(paths)) if p.is_file()])
    video = ROOT / 'videos/GX010021.MP4'
    commands = []
    def capture(args, name):
        commands.append(args)
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        (OUT / name).write_text(result.stdout, encoding='utf-8')
    capture(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(video)], 'ffprobe.json')
    capture(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-skip_frame', 'nokey', '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time,pict_type,key_frame', '-of', 'json', str(video)], 'keyframes.json')
    keydir = OUT / 'keyframe_images'
    keydir.mkdir()
    keyargs = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-skip_frame', 'nokey', '-i', str(video),
               '-map', '0:v:0', '-vf', 'scale=640:-2', '-fps_mode', 'vfr', '-q:v', '3', str(keydir / '%04d.jpg')]
    subprocess.run(keyargs, check=True, capture_output=True); commands.append(keyargs)
    keymeta = json.loads((OUT / 'keyframes.json').read_text(encoding='utf-8'))['frames']
    keyfiles = sorted(keydir.glob('*.jpg'))
    assert len(keyfiles) == len(keymeta)
    write_json(OUT / 'keyframe_image_index.json', [{'path':p.relative_to(OUT).as_posix(),
        'pts_seconds':float(meta['best_effort_timestamp_time']), 'sha256':sha(p),
        'content_review_status':'PENDING'} for p,meta in zip(keyfiles,keymeta)])
    frames = OUT / 'frames'
    frames.mkdir()
    args = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(video), '-map', '0:v:0', '-vf', "select='isnan(prev_selected_t)+gte(t-prev_selected_t,2)',scale=640:-2,showinfo", '-fps_mode', 'vfr', '-q:v', '3', str(frames / '%04d.jpg')]
    # select/showinfo are decoded frames, distinct from encoded I-frames recorded above.
    args[args.index('error')] = 'info'
    commands.append(args)
    r = subprocess.run(args, check=True, capture_output=True, text=True)
    (OUT / 'frame_extraction.log').write_text(r.stderr, encoding='utf-8')
    import re
    times = [float(t) for t in re.findall(r'Parsed_showinfo.*?\bn:\s*\d+.*?pts_time:([\d.]+)', r.stderr)]
    files = sorted(frames.glob('*.jpg'))
    assert len(files) == len(times), (len(files), len(times))
    write_json(OUT / 'frame_index.json', [{'path': p.relative_to(OUT).as_posix(), 'pts_seconds': t, 'sha256': sha(p)} for p,t in zip(files,times)])
    sheets = OUT / 'sheets'
    sheets.mkdir()
    # 20 frames per sheet, 40 seconds of coverage. Labels use actual decoded PTS.
    for offset in range(0,len(files),20):
        canvas = Image.new('RGB',(1600,1000),'#101820')
        draw = ImageDraw.Draw(canvas)
        for j,p in enumerate(files[offset:offset+20]):
            im = Image.open(p); im.thumbnail((400,225))
            x,y=(j%4)*400,(j//4)*200
            im.thumbnail((400,175)); canvas.paste(im,(x,y+22))
            draw.text((x+5,y+4),f'{offset+j+1:04d} | PTS {times[offset+j]:.3f}s',fill='white')
        canvas.save(sheets / f'{offset//20+1:02d}.jpg',quality=90)
    write_json(OUT / 'extraction_commands.json', commands)
    print(f'{len(files)} frames, {len(list(sheets.glob("*.jpg")))} sheets: {OUT}')

if __name__ == '__main__':
    main()
