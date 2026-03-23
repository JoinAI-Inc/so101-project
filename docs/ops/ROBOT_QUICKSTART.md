# ROBOT_QUICKSTART.md

目标：1 分钟内恢复 SO101 + LeRobot + PC Camera 基本运行链路。

## 1. 激活环境
```bash
conda activate <your_lerobot_env>
```

## 2. 检查依赖
```bash
python -c "import lerobot; print('lerobot ok')"
python -c "import deepdiff; print('deepdiff ok')"
```

缺 `deepdiff` 就装：
```bash
pip install deepdiff
```

## 3. 检查机械臂串口
```bash
ls /dev/ttyACM*
```

## 4. 检查 Windows 相机快照
```bash
curl -I http://172.25.0.1:5000/snapshot
```

## 5. 先做真机动作测试
```bash
python /mnt/e/OpenClaw_Config/workspace_DD/test_so101_torque_and_move.py
```

## 6. 进入键盘 teleop
```bash
/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python /mnt/e/SO101_Project/scripts/teleop/teleop_so101_keyboard.py
```

## 7. 如果要录视频 / 录状态
- `m`：开始/停止录制
- `p`：保存单张快照

录制文件在：
```bash
/mnt/e/so101_keyboard_recordings/
```
