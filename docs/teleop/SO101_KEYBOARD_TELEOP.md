# SO101_KEYBOARD_TELEOP.md

更新时间：2026-03-24

这份文档用于固化当前这套 **WSL + SO101 + 键盘 teleop** 工作流，方便后续快速恢复、部署和启动。

---

## 1. 目标

当前目标不是恢复完整 leader arm / 手柄 / 视觉闭环，而是：

**用键盘在 WSL 中直接控制 SO101 机械臂，完成调试、抓取演示和基础录制。**

这套方案适合：
- 快速测试机械臂是否可控
- 录制抓橘子之类的 demo
- 没有 leader arm 时做临时 teleop
- 后续扩展成手柄 / 视觉版本前的最小可用入口

---

## 2. 当前关键文件

### 主脚本
- `/mnt/e/SO101_Project/scripts/teleop/teleop_so101_keyboard.py`

### 相关恢复文档
- `/mnt/e/ROBOT_COLDSTART_RUNBOOK.md`
- `/mnt/e/ROBOT_QUICKSTART.md`

### 录制输出目录
- `/mnt/e/so101_keyboard_recordings/`

---

## 3. 当前已验证环境

当前可用 Python 环境不是 `/home/node/openpi/.venv`，而是：

- `/mnt/e/OpenClaw_Config/workspace_DD/.venv`

已实际验证：
- `lerobot` 可 import
- `deepdiff` 可 import

### 验证命令
```bash
/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python -c "import lerobot; print('lerobot ok')"
/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python -c "import deepdiff; print('deepdiff ok')"
```

---

## 4. 启动前检查

### 4.1 检查机械臂串口
```bash
ls /dev/ttyACM*
```

期望至少看到：
```bash
/dev/ttyACM0
```

如果没有：
- 检查 SO101 是否接入
- 检查 USB 是否透传到 WSL

### 4.2 相机不是必须
当前这套键盘 teleop：
- **不依赖 camera attach 到 WSL**
- 就算 Windows 相机还在 Windows 侧，也不影响控机械臂
- 当前脚本默认已经按“无相机模式”处理

所以：
- **先控机械臂，再考虑 camera**

---

## 5. 启动命令

### 直接启动
```bash
/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python /mnt/e/teleop_so101_keyboard.py
```

### 或先激活再启动
```bash
source /mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/activate
python /mnt/e/teleop_so101_keyboard.py
```

---

## 6. 当前脚本行为

启动后会：
1. 通过 `SO101FollowerConfig` 构建机器人对象
2. 用 `connect(calibrate=False)` 连接 SO101
3. 读取当前关节状态作为 `start_pose`
4. 进入键盘 teleop 循环
5. 持续发送目标位姿，实现连续控制

如果连接成功，通常会看到类似输出：
```text
✅ Robot created via config: SO101FollowerConfig
ℹ️ connect(calibrate=False)
```

---

## 7. 当前控制模式

当前已经从“单次按键一次动作”改成：

- **连续控制**
- **短时间多键并行响应**
- **WASD 风格主控**

也就是说：
- 不再是纯单关节离散跳动
- 更像在控制机械臂整体运动趋势

---

## 8. 当前按键映射

## 8.1 主控（WASD 风格）
- `w / s`：主前后风格动作
  - 联动 `shoulder_lift + elbow_flex`
- `a / d`：主左右风格动作
  - 主要控制 `shoulder_pan`

## 8.2 辅助控制
- `i / k`：接近 / 后撤微调
  - 联动 `elbow_flex + wrist_flex`
- `j / l`：`wrist_roll - / +`
- `n / m`：夹爪开合

## 8.3 细调备用
- `q / e`：`shoulder_pan` 细调
- `r / f`：`wrist_flex` 细调
- `t / g`：`gripper` 细调

## 8.4 功能键
- `1 / 2 / 3`：慢速 / 中速 / 快速
- `z`：回到初始位
- `u`：抬升辅助
- `o`：开始 / 停止录制
- `p`：保存单张快照
- `x`：退出

---

## 9. 推荐操作方式

### 第一次测试
建议先这样：

1. 切慢速
```text
1
```

2. 先试主控
- `w`
- `s`
- `a`
- `d`

3. 再试夹爪
- `n`
- `m`

4. 再试辅助微调
- `i / k`
- `j / l`

### 如果发现方向不顺
不要自己改代码，直接记录：
- 哪个键方向反了
- 哪个动作太快 / 太慢
- 哪个联动不自然

后续直接改脚本即可。

---

## 10. 录制功能

虽然当前不依赖 camera，但脚本仍保留录制状态日志能力。

### 开始 / 停止录制
```text
o
```

### 保存内容
每次录制会生成一个 episode 目录，例如：
- `/mnt/e/so101_keyboard_recordings/ep_000/`
- `/mnt/e/so101_keyboard_recordings/ep_001/`

其中包含：
- `states.json`
- `meta.json`
- 如果未来开启相机，还可以有 `images/`

### 当前日志记录内容
- 时间戳
- 当前 observation
- 当前 target
- 当前 active_keys

---

## 11. 常见问题

### 11.1 相机 warning
如果看到相机相关 warning：
- 当前版本已默认关闭本地 camera 打开
- 即使没有 camera，也不影响机械臂控制

### 11.2 缺依赖
如果误用了错误 Python 环境，可能会报：
- `No module named lerobot`
- `No module named deepdiff`

解决方法：
- 不要用系统默认 `python3`
- 直接用：
```bash
/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python
```

### 11.3 找不到串口
如果 `/dev/ttyACM0` 不存在：
- 优先检查 USB / WSL 透传
- 不要先怀疑 teleop 脚本

---

## 12. 最短启动流程

```bash
ls /dev/ttyACM*
/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python /mnt/e/teleop_so101_keyboard.py
```

如果脚本启动后看到：
- robot created 成功
- connect 成功
- 初始状态打印出来

那就说明键盘 teleop 链路已通。

---

## 13. 当前版本状态

当前版本已经支持：
- SO101 连接
- 键盘连续控制
- 多键并行响应
- WASD 风格主控
- 回初始位
- 抬升辅助
- 录制状态日志

当前暂不优先处理：
- camera attach 到 WSL
- 网络相机录制
- 手柄版 teleop
- 更复杂 IK 笛卡尔控制

---

## 14. 后续建议

后续如需升级，可以按这个顺序：

1. 调顺 WASD 键感
2. 固化安全限位
3. 调整 gripper 开合方向与幅度
4. 补网络 snapshot 相机录制
5. 如仍不够自然，再考虑手柄版或笛卡尔控制版

---

## 15. 一句话总结

当前这套键盘 teleop 的最短可用命令是：

```bash
/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python /mnt/e/teleop_so101_keyboard.py
```

只要 SO101 串口在 WSL 可见，就可以先不管相机，直接开始控机械臂。
```

只要 SO101 串口在 WSL 可见，就可以先不管相机，直接开始控机械臂。
