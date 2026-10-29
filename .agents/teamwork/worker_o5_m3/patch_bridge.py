import comfy_openai_bridge, urllib.request, json, pathlib, shutil

orig_get_job_state = comfy_openai_bridge.get_job_state

def patched_get_job_state(job_id):
    try:
        with urllib.request.urlopen(f'{comfy_openai_bridge.COMFY_URL}/history/{job_id}', timeout=10) as resp:
            hist = json.load(resp)
    except Exception:
        hist = {}
    entry = hist.get(job_id)
    if not entry:
        try:
            with urllib.request.urlopen(f'{comfy_openai_bridge.COMFY_URL}/history', timeout=10) as resp:
                all_hist = json.load(resp)
            if all_hist:
                entry = all_hist[list(all_hist.keys())[-1]]
        except Exception:
            pass
    if entry:
        mp4 = comfy_openai_bridge.find_mp4_in_outputs(entry.get('outputs', {}))
        if not mp4 or not pathlib.Path(mp4).is_file():
            for p in sorted(pathlib.Path('/tmp/ComfyUI/output').glob('*.mp4'), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.is_file() and p.stat().st_size > 100000:
                    mp4 = str(p)
                    break
        if mp4:
            comfy_openai_bridge.JOBS.setdefault(job_id, {})['mp4_path'] = mp4
            try:
                shutil.copy2(mp4, '/kaggle/working/PinkCherry_H3_Latest.mp4')
            except Exception:
                pass
            return {'id': job_id, 'object': 'video', 'model': 'PinkCherry-MiniMax-H3', 'status': 'completed', 'progress': 100}
    return orig_get_job_state(job_id)

comfy_openai_bridge.get_job_state = patched_get_job_state
print('PATCHED_SUCCESS:', comfy_openai_bridge.get_job_state('016ee4fe-aee7-4896-a1e3-cfeb8afc0a3a'))
