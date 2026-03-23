# SO101_Project

统一入口：整理 SO101 机械臂相关的**冷启动、键盘 teleop、诊断、deploy、数据处理与训练文档**。

## 目录结构

- `docs/ops/`
  - `ROBOT_COLDSTART_RUNBOOK.md`
  - `ROBOT_QUICKSTART.md`
- `docs/teleop/`
  - `SO101_KEYBOARD_TELEOP.md`
- `docs/training/`
  - `ROBOT_STRATEGY_LEROBOT_SO101.md`
- `scripts/teleop/`
  - `teleop_so101_keyboard.py`
- `scripts/diagnostics/`
  - `diag_so101_io.py`
  - `test_so101_torque_and_move.py`
  - `test_so101_action_path.py`
- `scripts/deploy/`
  - `deploy_openclaw.py`
  - `deploy_openclaw_safe_v2.py`
  - `deploy_openclaw_debug_v3.py`
- `scripts/data/`
  - `record_episode.py`
  - `convert_to_lerobot.py`
  - `convert_lerobot_v2.py`
  - `rebuild_dataset_delta.py`
  - `rebuild_dataset_delta_subset.py`
  - `build_reach_only_subset.py`
- `records/`
  - 建议放键盘 teleop 录制结果
- `snapshots/`
  - 项目快照索引与说明
- `data/`
  - 数据集入口说明（大数据暂不复制）

## 当前统一启动命令

```bash
/mnt/e/OpenClaw_Config/workspace_DD/.venv/bin/python /mnt/e/SO101_Project/scripts/teleop/teleop_so101_keyboard.py
```

## 相关外部/原始资源（保留原位）

以下大体积资源暂时不复制，统一在文档中引用原路径：

- 工作区：`/mnt/e/OpenClaw_Config/workspace_DD`
- 快照目录：`/mnt/e/OpenClaw_Config/workspace_DD/_snapshot_20260320`
- 快照压缩包：`/mnt/e/OpenClaw_Config/workspace_DD/openclaw_snapshot_20260320.tar.gz`
- 可用 venv：`/mnt/e/OpenClaw_Config/workspace_DD/.venv`
- 键盘录制输出：`/mnt/e/so101_keyboard_recordings`

## 建议后续拆分仓库

1. `so101-ops`：冷启动 / teleop / 诊断 / deploy
2. `so101-training`：数据处理 / 数据集 / 训练 / 策略文档
3. `so101-assets`：大模型、快照、数据集（可选，不一定进 git）
