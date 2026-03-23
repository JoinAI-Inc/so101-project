import os
import json
import cv2
import torch
import numpy as np
from tqdm import tqdm
from datasets import Dataset, Features, Sequence, Image, Value

print("🧪 [Join AI] 正在将原始数据炼制为 LeRobot 标准格式...")

DATA_DIR = "/home/node/.openclaw/workspace_DD/dataset"
OUTPUT_DIR = "/home/node/.openclaw/workspace_DD/lerobot_dataset_orange"

# 1. 扫描所有录制好的 Episode
episodes = sorted([d for d in os.listdir(f"{DATA_DIR}/images") if d.startswith("ep_")])
all_data = []

for ep_name in tqdm(episodes, desc="读取数据"):
    img_dir = f"{DATA_DIR}/images/{ep_name}"
    json_path = f"{DATA_DIR}/states/{ep_name}.json"
    
    with open(json_path, "r") as f:
        states = json.load(f)
    
    img_files = sorted(os.listdir(img_dir))
    
    # 确保图片和坐标数量对齐
    num_frames = min(len(img_files), len(states))
    
    for i in range(num_frames):
        img_path = f"{img_dir}/{img_files[i]}"
        # 将坐标归一化 (LeRobot 习惯使用 -1 到 1，但我们先保持原始并记录范围)
        # 注意：Pi-0 训练通常需要 [6] 维 Action
        state_array = np.array(states[i], dtype=np.float32)
        
        all_data.append({
            "observation.images.base_0_rgb": img_path, # 先存路径，后面 Dataset 会自动处理
            "observation.state": state_array,
            "action": state_array, # 在模仿学习中，当前时刻的 Action 就是下一时刻的目标状态
            "episode_index": int(ep_name.split("_")[1]),
            "frame_index": i,
        })

# 2. 定义 Hugging Face 数据集特征
features = Features({
    "observation.images.base_0_rgb": Image(),
    "observation.state": Sequence(Value("float32"), length=6),
    "action": Sequence(Value("float32"), length=6),
    "episode_index": Value("int64"),
    "frame_index": Value("int64"),
})

# 3. 创建并保存
dataset = Dataset.from_list(all_data, features=features)
dataset.save_to_disk(OUTPUT_DIR)

print(f"\n✅ 转换完成！数据集已存至: {OUTPUT_DIR}")
print(f"📊 总帧数: {len(all_data)}，总 Episode: {len(episodes)}")
