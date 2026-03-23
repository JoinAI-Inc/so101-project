#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import argparse
import numpy as np
import torch
from PIL import Image
from tqdm import tqdm
from lerobot.datasets.lerobot_dataset import LeRobotDataset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data_dir', required=True)
    ap.add_argument('--out_dir', required=True)
    ap.add_argument('--repo_id', default='join-ai/so101-orange-delta-subset')
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--horizon', type=int, default=6)
    ap.add_argument('--static_eps', type=float, default=0.8)
    ap.add_argument('--task', default='pick an orange and place on the plate')
    args = ap.parse_args()

    img_root = os.path.join(args.data_dir, 'images')
    state_root = os.path.join(args.data_dir, 'states')
    eps = sorted(d for d in os.listdir(img_root) if d.startswith('ep_') and os.path.isdir(os.path.join(img_root, d)))
    if not eps:
        raise RuntimeError(f'No episodes found under {img_root}')

    sample_ep = eps[0]
    sample_dir = os.path.join(img_root, sample_ep)
    first = sorted(os.listdir(sample_dir))[0]
    w, h = Image.open(os.path.join(sample_dir, first)).size

    features = {
        'observation.images.base_0_rgb': {'dtype': 'image', 'shape': (3, h, w), 'names': ['c', 'h', 'w']},
        'observation.state': {'dtype': 'float32', 'shape': (6,), 'names': ['dim']},
        'action': {'dtype': 'float32', 'shape': (6,), 'names': ['dim']},
    }

    ds = LeRobotDataset.create(
        repo_id=args.repo_id,
        root=args.out_dir,
        features=features,
        fps=args.fps,
        robot_type='so101',
    )

    kept, dropped = 0, 0
    for ep in tqdm(eps, desc='pack_subset'):
        img_dir = os.path.join(img_root, ep)
        state_path = os.path.join(state_root, f'{ep}.json')
        if not os.path.exists(state_path):
            continue

        states = np.asarray(json.load(open(state_path, 'r', encoding='utf-8')), dtype=np.float32)
        imgs = sorted(os.listdir(img_dir))
        n = min(len(imgs), len(states))
        if n < 2:
            continue

        for i in range(n):
            j = min(i + args.horizon, n - 1)
            s = states[i]
            sj = states[j]
            a = sj - s
            if np.linalg.norm(a) < args.static_eps:
                dropped += 1
                continue

            img = Image.open(os.path.join(img_dir, imgs[i])).convert('RGB')
            ds.add_frame({
                'observation.images.base_0_rgb': img,
                'observation.state': torch.tensor(s, dtype=torch.float32),
                'action': torch.tensor(a, dtype=torch.float32),
                'task': args.task,
            })
            kept += 1

        ds.save_episode()

    if hasattr(ds, 'consolidate'):
        ds.consolidate()
    elif hasattr(ds, 'compute_stats'):
        ds.compute_stats()
    elif hasattr(ds, 'save_meta_data'):
        ds.save_meta_data()

    print(json.dumps({
        'out_dir': args.out_dir,
        'episodes': len(eps),
        'kept_frames': kept,
        'dropped_frames': dropped,
        'task': args.task,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
