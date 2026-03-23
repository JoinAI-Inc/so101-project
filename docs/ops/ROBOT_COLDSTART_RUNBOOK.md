# ROBOT_COLDSTART_RUNBOOK.md

更新时间：2026-03-23

这份文档用于恢复当前这套 **WSL + LeRobot + SO101 + Windows PC Camera** 链路。
目标不是解释原理，而是让下次冷启动时尽快恢复可运行状态。

---

## 1. 当前整体架构

### Windows 侧
- 提供 PC camera 快照服务
- 已验证过的快照接口：
  - `http://172.25.0.1:5000/snapshot`
- 旧记录里也出现过一个可用地址：
  - `http://192.168.1.3:5000/snapshot`
- 说明：IP 可能会变，核心是 **Windows 上的 snapshot server 要先启动**

### WSL 侧
- 负责运行 LeRobot / Python 控制脚本
- 负责连接 SO101 串口设备：
  - 典型设备：`/dev/ttyACM0`
- 负责 deploy / record / teleop / 推理

### 机器人
- 型号：SO101
- 已确认：`send_action()` 链路能驱动真机

---

## 2. 当前已知有效路径

### 工作区
- 主工作区：`/mnt/e/OpenClaw_Config/workspace_DD`

### 快照目录
- `/_snapshot_20260320` 内保留了一次重要快照：
  - `/mnt/e/OpenClaw_Config/workspace_DD/_snapshot_20260320`

### calibration
- 已发现 calibration 文件：
  - `/mnt/e/OpenClaw_Config/workspace_DD/_snapshot_20260320/calibration/so_follower/my_awesome_follower_arm.json`

### deploy 脚本
- 快照内 deploy：
  - `/mnt/e/OpenClaw_Config/workspace_DD/_snapshot_20260320/deploy_openclaw.py`
- 工作区内 deploy：
  - `/mnt/e/OpenClaw_Config/workspace_DD/deploy_openclaw.py`
  - `/mnt/e/OpenClaw_Config/workspace_DD/deploy_openclaw_safe_v2.py`
  - `/mnt/e/OpenClaw_Config/workspace_DD/deploy_openclaw_debug_v3.py`

### 诊断 / 控制相关脚本
- `/mnt/e/OpenClaw_Config/workspace_DD/diag_so101_io.py`
- `/mnt/e/OpenClaw_Config/workspace_DD/test_so101_torque_and_move.py`
- `/mnt/e/OpenClaw_Config/workspace_DD/test_so101_action_path.py`
- `/mnt/e/SO101_Project/scripts/teleop/teleop_so101_keyboard.py`

---

## 3. 这条链路之前已经验证过什么

根据本地记录，已经验证过：

1. WSL 能访问 SO101
   - 串口路径用过 `/dev/ttyACM0`

2. `send_action()` 可用
   - 已在真机上做过 shoulder_pan +20 的动作测试

3. torque 可启用
   - 之前已做过 torque / move 测试

4. Windows camera gateway 能工作
   - WSL 可通过 HTTP snapshot 拉图

5. 真正卡点不是硬件链路，而是策略/数据质量
   - 模型会动，但经常方向不对

---

## 4. 冷启动时先确认的 4 件事

### A. 机械臂串口是否出现
```bash
ls /dev/ttyACM*
```

如果没有：
- 先检查 USB 是否接好
- 检查是否已透传到 WSL
- 没串口时，不要继续折腾上层脚本

### B. Windows 相机快照是否可访问
在 WSL 里测试：
```bash
curl -I http://172.25.0.1:5000/snapshot
```

如果 172.25.0.1 不通，再按实际 Windows IP 改。

### C. Python / LeRobot 环境是否正确
先激活你们实际使用的 conda / venv 环境，再检查：
```bash
python -c "import lerobot; print('lerobot ok')"
python -c "import deepdiff; print('deepdiff ok')"
```

如果第二句报错：
```bash
pip install deepdiff
```

### D. calibration 文件是否还在
```bash
ls /mnt/e/OpenClaw_Config/workspace_DD/_snapshot_20260320/calibration/so_follower/
```

---

## 5. 推荐恢复顺序

### Step 1：进入正确环境
优先激活你们之前跑 SO101 / LeRobot 的环境：
```bash
conda activate <your_lerobot_env>
```

如果不确定环境名：
```bash
conda env list
```

### Step 2：检查基础依赖
```bash
python -c "import lerobot; print('lerobot ok')"
python -c "import deepdiff; print('deepdiff ok')"
```

### Step 3：检查串口
```bash
ls /dev/ttyACM*
```

### Step 4：检查 camera snapshot
```bash
curl -I http://172.25.0.1:5000/snapshot
```

### Step 5：做 SO101 I/O 诊断
```bash
python /mnt/e/OpenClaw_Config/workspace_DD/diag_so101_io.py
```

### Step 6：做动作链路测试
```bash
python /mnt/e/OpenClaw_Config/workspace_DD/test_so101_torque_and_move.py
```

### Step 7：进入 teleop / deploy
键盘 teleop：
```bash
python /mnt/e/teleop_so101_keyboard.py
```

如需模型 deploy，再根据实际模型路径选择：
```bash
python /mnt/e/OpenClaw_Config/workspace_DD/deploy_openclaw_safe_v2.py
```
或
```bash
python /mnt/e/OpenClaw_Config/workspace_DD/_snapshot_20260320/deploy_openclaw.py
```

---

## 6. 最短恢复路径

如果目标只是尽快恢复到“人控能动 SO101”：

1. 激活 LeRobot 环境
2. 确认 `/dev/ttyACM0` 存在
3. 确认 snapshot 服务可访问
4. 跑：
```bash
python /mnt/e/OpenClaw_Config/workspace_DD/test_so101_torque_and_move.py
```
5. 再跑：
```bash
python /mnt/e/teleop_so101_keyboard.py
```

---

## 7. 常见坑

### 坑 1：当前环境不是正确的 LeRobot 环境
症状：
- `import lerobot` 报错
- 或缺 `deepdiff`

修复：
- 先激活正确环境
- 再在那个环境里补装缺包

### 坑 2：WSL 里没有 `/dev/ttyACM0`
症状：
- 脚本能启动，但连不上机械臂

修复：
- 优先检查 USB 透传，不要先怀疑上层逻辑

### 坑 3：Windows camera IP 变了
症状：
- snapshot URL 超时

修复：
- 重新确认 Windows 当前 IP
- 只要 snapshot server 在，IP 变动是正常的

### 坑 4：模型能动但方向不对
这不是控制链路问题，是数据 / 策略问题。
不要把部署 bug 和策略 bug 混在一起查。

---

## 8. 当前与橘子任务相关的重要背景

- 当前任务主线是 SO101 抓橘子
- 旧数据集和模型命名里已经有：
  - `join-ai/so101-orange`
  - `join-ai/so101-orange-dataset`
- 之前的结论是：
  - 硬件链路通
  - 模型方向映射不稳定
  - 所以才会转向 teleop / 更小任务拆解

---

## 9. 现在最推荐的操作策略

如果目标是先拿到 demo：
- 不要先折腾复杂模型
- 先恢复 teleop
- 先录一条抓橘子视频
- 后面再处理策略训练

---

## 10. 恢复后建议补做的事

1. 把实际使用的 conda 环境名写进本文档
2. 把 Windows camera 启动命令写进本文档
3. 把最终稳定的 deploy 命令写进本文档
4. 如果确认有新 calibration 路径，也写进本文档
写进本文档
