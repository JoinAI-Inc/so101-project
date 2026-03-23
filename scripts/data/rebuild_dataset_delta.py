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
    ap.add_argument("--data_dir", required=True)      # 原始: images/ + states/
    ap.add_argument("--out_dir", required=True)       # 新数据集输出目录
    ap.add_argument("--repo_id", default="join-ai/so101-orange-delta")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--horizon", type=int, default=6) # 建议 4~8
    ap.add_argument("--static_eps", type=float, default=0.8)  # 过滤静止帧阈值
    ap.add_argument("--task", default="pick up the orange")
    args = ap.parse_args()

    sample = os.path.join(args.data_dir, "images", "ep_0")
    first = sorted(os.listdir(sample))[0]
    w, h = Image.open(os.path.join(sample, first)).size

    features = {
        "observation.images.base_0_rgb": {"dtype": "image", "shape": (3, h, w), "names": ["c", "h", "w"]},
        "observation.state": {"dtype": "float32", "shape": (6,), "names": ["dim"]},
        "action": {"dtype": "float32", "shape": (6,), "names": ["dim"]},
    }

    ds = LeRobotDataset.create(
        repo_id=args.repo_id,
        root=args.out_dir,
        features=features,
        fps=args.fps,
        robot_type="so101",
    )

    eps = sorted(d for d in os.listdir(os.path.join(args.data_dir, "images")) if d.startswith("ep_"))
    kept, dropped = 0, 0

    for ep in tqdm(eps, desc="pack"):
        img_dir = os.path.join(args.data_dir, "images", ep)
        state_path = os.path.join(args.data_dir, "states", f"{ep}.json")
        if not os.path.exists(state_path):
            continue

        states = np.asarray(json.load(open(state_path, "r", encoding="utf-8")), dtype=np.float32)
        imgs = sorted(os.listdir(img_dir))
        n = min(len(imgs), len(states))
        if n < 2:
            continue

        for i in range(n):
            j = min(i + args.horizon, n - 1)
            s = states[i]
            sj = states[j]
            a = sj - s  # 核心：delta action

            if np.linalg.norm(a) < args.static_eps:
                dropped += 1
                continue

            img = Image.open(os.path.join(img_dir, imgs[i])).convert("RGB")
            ds.add_frame(
                {
                    "observation.images.base_0_rgb": img,
                    "observation.state": torch.tensor(s, dtype=torch.float32),
                    "action": torch.tensor(a, dtype=torch.float32),
                    "task": args.task,
                }
            )
            kept += 1

        ds.save_episode()

    # lerobot 0.4.4 兼容
    if hasattr(ds, "consolidate"):
        ds.consolidate()
    elif hasattr(ds, "compute_stats"):
        ds.compute_stats()
    elif hasattr(ds, "save_meta_data"):
        ds.save_meta_data()

    print(f"done: {args.out_dir}")



if __name__ == "__main__":
    main()
