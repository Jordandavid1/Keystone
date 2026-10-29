RUN_ATOMIC_VIDEO = True
ATOMIC_PROMPT = 'A cinematic aerial view of a quiet mountain lake at sunrise'
ATOMIC_MODEL = 'PinkCherry-MiniMax-H3'
if RUN_ATOMIC_VIDEO:
    payload = {'prompt': ATOMIC_PROMPT, 'seconds': '4', 'size': '1280x720'}
    if ATOMIC_MODEL:
        payload['model'] = ATOMIC_MODEL
    response = atomic.post(f'{ATOMIC_BASE_URL}/videos', json=payload, timeout=60)
    response.raise_for_status()
    job_info = response.json()
    job_id = job_info.get('id')
    print('Atomic Chat queued job:', job_id, 'status:', job_info.get('status'))
    
    # Poll until completed
    import time
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        poll_resp = atomic.get(f'{ATOMIC_BASE_URL}/videos/{job_id}', timeout=30)
        poll_data = poll_resp.json()
        status = poll_data.get('status')
        progress = poll_data.get('progress')
        print(f'Job {job_id} status: {status} progress: {progress}%')
        if status in ('completed', 'failed'):
            break
        time.sleep(3)
