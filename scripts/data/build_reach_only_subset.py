#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import shutil
from pathlib import Path
import numpy as np

WORKDIR = Path('/mnt/e/OpenClaw_Config/workspace_DD')
SRC = WORKDIR / 'dataset_clean_subset_A'
DST = WORKDIR / 'dataset_reach_only_subset_A'
PLAN = WORKDIR / 'dataset_subset_plan.json'
GRIP_THRESHOLD = 60.0
MIN_FRAMES = 40
PRE_CLOSE_BUFFER = 8


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    selected = plan['selected_group_a']

    if DST.exists():
        shutil.rmtree(DST)
    (DST / 'images').mkdir(parents=True, exist_ok=True)
    (DST / 'states').mkdir(parents=True, exist_ok=True)

    summary = []
    for ep in selected:
        state_path = SRC / 'states' / f'{ep}.json'
        img_dir = SRC / 'images' / ep
        if not state_path.exists() or not img_dir.exists():
            continue

        states = np.asarray(json.loads(state_path.read_text(encoding='utf-8')), dtype=np.float32)
        images = sorted(p.name for p in img_dir.iterdir() if p.is_file())
        n = min(len(states), len(images))
        states = states[:n]
        images = images[:n]

        grip = states[:, 5]
        close_idx = np.where(grip < GRIP_THRESHOLD)[0]
        cut = int(close_idx[0] - PRE_CLOSE_BUFFER) if len(close_idx) else n - 1
        cut = max(MIN_FRAMES, min(cut, n - 1))
        keep_n = cut + 1

        out_img_dir = DST / 'images' / ep
        out_img_dir.mkdir(parents=True, exist_ok=True)
        for name in images[:keep_n]:
            shutil.copy2(img_dir / name, out_img_dir / name)
        (DST / 'states' / f'{ep}.json').write_text(
            json.dumps(states[:keep_n].tolist(), ensure_ascii=False),
            encoding='utf-8',
        )

        summary.append({
            'ep': ep,
            'original_frames': int(n),
            'kept_frames': int(keep_n),
            'close_idx': int(close_idx[0]) if len(close_idx) else None,
            'cut_idx': int(cut),
        })

    out = {
        'source_dataset': str(SRC),
        'output_dataset': str(DST),
        'grip_threshold': GRIP_THRESHOLD,
        'pre_close_buffer': PRE_CLOSE_BUFFER,
        'min_frames': MIN_FRAMES,
        'episodes': summary,
    }
    (DST / 'reach_subset_summary.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
