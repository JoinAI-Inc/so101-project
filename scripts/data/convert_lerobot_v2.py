import os
import json
import torch
from PIL import Image
from tqdm import tqdm
from lerobot.datasets.lerobot_dataset import LeRobotDataset

print("🧪 [Join AI] 正在炼制 LeRobot 专属数据集 (生成 Meta 元数据)...")

DATA_DIR = "/home/node/.openclaw/workspace_DD/dataset"
OUTPUT_DIR = "/home/node/.openclaw/workspace_DD/lerobot_dataset_v2"
REPO_ID = "join-ai/so101-orange-dataset"

# 1. 自动获取你的真实图片尺寸
sample_dir = f"{DATA_DIR}/images/ep_0"
sample_img = os.path.join(sample_dir, os.listdir(sample_dir)[0])
with Image.open(sample_img) as img:
    w, h = img.size

# 2. 定义 LeRobot 专属的特征字典 (严格对齐传感器要求)
features = {
    "observation.images.base_0_rgb": {
        "dtype": "image",
        "shape": (3, h, w),  # 👈 换成圆括号 tuple
        "names": ["c", "h", "w"]
    },
    "observation.state": {
        "dtype": "float32",
        "shape": (6,),       # 👈 换成圆括号 tuple，注意里面有个逗号
        "names": ["dim"]
    },
    "action": {
        "dtype": "float32",
        "shape": (6,),       # 👈 换成圆括号 tuple，注意里面有个逗号
        "names": ["dim"]
    }
}

# 3. 创建 LeRobotDataset 实例
dataset = LeRobotDataset.create(
    repo_id=REPO_ID,
    root=OUTPUT_DIR,
    features=features,
    fps=30,
    robot_type="so101"
)

episodes = sorted([d for d in os.listdir(f"{DATA_DIR}/images") if d.startswith("ep_")])

# 4. 逐帧灌入数据
for ep_name in tqdm(episodes, desc="打包 Episode"):
    img_dir = f"{DATA_DIR}/images/{ep_name}"
    json_path = f"{DATA_DIR}/states/{ep_name}.json"
    
    with open(json_path, "r") as f:
        states = json.load(f)
        
    img_files = sorted(os.listdir(img_dir))
    num_frames = min(len(img_files), len(states))
    
    for i in range(num_frames):
        img_path = f"{img_dir}/{img_files[i]}"
        img = Image.open(img_path).convert("RGB")
        
        # 模仿学习的核心：当前帧的动作，是为了达到下一帧的状态
        action_idx = min(i + 1, num_frames - 1)
        
        frame_dict = {
            "observation.images.base_0_rgb": img,
            "observation.state": torch.tensor(states[i], dtype=torch.float32),
            "action": torch.tensor(states[action_idx], dtype=torch.float32),
            "task": "pick up the orange"  # 👈 加上这行文本指令！
        }
        dataset.add_frame(frame_dict)
        
    dataset.save_episode()

# 5. 这行代码最关键：它会自动计算 stats.json 和 info.json！
dataset.consolidate()
print(f"\n✅ 转换完成！带 Meta 元数据的数据集已存至: {OUTPUT_DIR}")
