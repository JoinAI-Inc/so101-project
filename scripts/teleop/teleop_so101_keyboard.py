#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import json
import importlib
import inspect
import termios
import tty
import select
from pathlib import Path

import numpy as np

try:
    import cv2
except Exception:
    cv2 = None


JOINT_KEYS = {
    # WASD main teleop style
    "w": {"shoulder_lift.pos": -1.0, "elbow_flex.pos": -0.8},
    "s": {"shoulder_lift.pos":  1.0, "elbow_flex.pos":  0.8},
    "a": {"shoulder_pan.pos":   1.0},
    "d": {"shoulder_pan.pos":  -1.0},

    # vertical / approach refinement
    "i": {"elbow_flex.pos":    -1.0, "wrist_flex.pos":  0.4},
    "k": {"elbow_flex.pos":     1.0, "wrist_flex.pos": -0.4},
    "j": {"wrist_roll.pos":    -1.0},
    "l": {"wrist_roll.pos":     1.0},

    # gripper
    "n": {"gripper.pos":       -1.0},
    "m": {"gripper.pos":        1.0},

    # fine joint fallback
    "q": {"shoulder_pan.pos":  -1.0},
    "e": {"shoulder_pan.pos":   1.0},
    "r": {"wrist_flex.pos":    -1.0},
    "f": {"wrist_flex.pos":     1.0},
    "t": {"gripper.pos":       -1.0},
    "g": {"gripper.pos":        1.0},
}

JOINT_ORDER = [
    "shoulder_pan.pos",
    "shoulder_lift.pos",
    "elbow_flex.pos",
    "wrist_flex.pos",
    "wrist_roll.pos",
    "gripper.pos",
]

STEP_PRESETS = {
    "1": 1.0,
    "2": 3.0,
    "3": 6.0,
}

DATASET_ROOT = Path("/mnt/e/so101_keyboard_recordings")
SNAPSHOT_EVERY_N_FRAMES = 3
ACTIVE_KEY_HOLD_SEC = 0.18
CONTROL_HZ = 30


def build_so_robot(port="/dev/ttyACM0", robot_id="my_awesome_follower_arm"):
    try:
        robots_mod = importlib.import_module("lerobot.robots")
        so_mod = importlib.import_module("lerobot.robots.so_follower")
    except ModuleNotFoundError as e:
        missing = getattr(e, "name", "unknown")
        raise RuntimeError(
            f"缺少 Python 依赖: {missing}。\n"
            f"先在当前环境安装它，例如:\n"
            f"  pip install {missing}\n"
            f"如果你是在 LeRobot/conda 环境里跑，建议直接在当前激活环境中安装后重试。"
        ) from e
    make_robot_from_config = robots_mod.make_robot_from_config

    for cfg_name in ("SO101FollowerConfig", "SO100FollowerConfig", "SOFollowerRobotConfig"):
        if not hasattr(so_mod, cfg_name):
            continue
        cfg_cls = getattr(so_mod, cfg_name)
        try:
            sig = inspect.signature(cfg_cls)
            kwargs = {}
            if "type" in sig.parameters:
                kwargs["type"] = "so_follower"
            if "port" in sig.parameters:
                kwargs["port"] = port
            if "id" in sig.parameters:
                kwargs["id"] = robot_id
            if "cameras" in sig.parameters:
                kwargs["cameras"] = {}
            if "follower_arms" in sig.parameters:
                kwargs["follower_arms"] = {"main": port}

            cfg = cfg_cls(**kwargs)
            if not hasattr(cfg, "type"):
                setattr(cfg, "type", "so_follower")

            robot = make_robot_from_config(cfg)
            if robot is not None and hasattr(robot, "send_action"):
                print(f"✅ Robot created via config: {cfg_name}")
                return robot
        except Exception as e:
            print(f"skip {cfg_name}: {e!r}")

    raise RuntimeError("无法构建 SO101 robot")


def connect_robot(robot):
    sig = inspect.signature(robot.connect)
    if "calibrate" in sig.parameters:
        print("ℹ️ connect(calibrate=False)")
        return robot.connect(calibrate=False)
    return robot.connect()


def get_obs(robot):
    d = robot.get_observation()
    obs = {}
    for k in JOINT_ORDER:
        obs[k] = float(d[k])
    return obs


def clamp_target(target):
    limits = {
        "shoulder_pan.pos":  (-120, 120),
        "shoulder_lift.pos": (-30, 120),
        "elbow_flex.pos":    (-120, 120),
        "wrist_flex.pos":    (-120, 120),
        "wrist_roll.pos":    (-180, 180),
        "gripper.pos":       (0, 100),
    }
    out = {}
    for k, v in target.items():
        lo, hi = limits[k]
        out[k] = float(np.clip(v, lo, hi))
    return out


def send_target(robot, target):
    target = clamp_target(target)
    robot.send_action(target)


def move_smooth(robot, start, goal, duration=1.5, hz=30):
    steps = max(1, int(duration * hz))
    for i in range(1, steps + 1):
        alpha = i / steps
        cur = {}
        for k in JOINT_ORDER:
            cur[k] = (1 - alpha) * start[k] + alpha * goal[k]
        send_target(robot, cur)
        time.sleep(1.0 / hz)


def read_key_nonblocking(timeout=0.02):
    dr, _, _ = select.select([sys.stdin], [], [], timeout)
    if dr:
        return sys.stdin.read(1)
    return None


def print_help():
    print("\n===== SO101 Keyboard Teleop (WASD style) =====")
    print("w/s : main forward/back style motion")
    print("a/d : main left/right yaw style motion")
    print("i/k : approach / retract refinement")
    print("j/l : wrist roll -/+")
    print("n/m : gripper -/+")
    print("q/e : shoulder_pan fine -/+")
    print("r/f : wrist_flex fine -/+")
    print("t/g : gripper fine -/+")
    print("1/2/3 : slow/medium/fast")
    print("z : return to start pose")
    print("u : lift-up helper")
    print("p : save one snapshot")
    print("x : exit")
    print("=============================================\n")


def make_episode_dirs(ep_idx: int):
    ep_dir = DATASET_ROOT / f"ep_{ep_idx:03d}"
    img_dir = ep_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    return ep_dir, img_dir


def open_camera(index=0, enabled=False):
    if not enabled:
        return None
    if cv2 is None:
        print("⚠️ OpenCV 不可用，跳过相机录制")
        return None
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print("⚠️ 相机打开失败，跳过相机录制")
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return cap


def save_snapshot(cap, out_path: Path):
    if cap is None or cv2 is None:
        return False
    ok, frame = cap.read()
    if not ok:
        return False
    return bool(cv2.imwrite(str(out_path), frame))


def main():
    port = "/dev/ttyACM0"
    robot = build_so_robot(port=port)
    connect_robot(robot)

    current = get_obs(robot)
    target = dict(current)
    start_pose = dict(current)

    step_size = 3.0
    DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    cap = open_camera(0, enabled=False)

    is_recording = False
    episode_idx = 0
    frame_idx = 0
    state_log = []
    record_ep_dir = None
    record_img_dir = None
    active_joint_keys = {}
    control_period = 1.0 / CONTROL_HZ
    last_control_ts = time.time()

    print_help()
    print("初始状态:", current)
    print("当前步长:", step_size)
    print(f"录制目录: {DATASET_ROOT}")
    print("模式: 连续控制 / 支持短时间多键并行")

    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())

    try:
        while True:
            now = time.time()
            key = read_key_nonblocking(timeout=0.001)

            if key is not None:
                key = key.lower()

                if key in STEP_PRESETS:
                    step_size = STEP_PRESETS[key]
                    print(f"步长切换 -> {step_size}")
                    continue

                if key == "x":
                    print("退出 teleop")
                    break

                if key == "o":
                    if not is_recording:
                        record_ep_dir, record_img_dir = make_episode_dirs(episode_idx)
                        state_log = []
                        frame_idx = 0
                        is_recording = True
                        print(f"🎬 开始录制 ep_{episode_idx:03d}")
                    else:
                        meta = {
                            "episode_idx": episode_idx,
                            "step_size": step_size,
                            "start_pose": start_pose,
                            "final_target": dict(target),
                            "frames_logged": frame_idx,
                            "states_logged": len(state_log),
                            "camera_enabled": cap is not None,
                        }
                        with open(record_ep_dir / "states.json", "w", encoding="utf-8") as f:
                            json.dump(state_log, f, ensure_ascii=False, indent=2)
                        with open(record_ep_dir / "meta.json", "w", encoding="utf-8") as f:
                            json.dump(meta, f, ensure_ascii=False, indent=2)
                        is_recording = False
                        print(f"💾 已保存 ep_{episode_idx:03d} -> {record_ep_dir}")
                        episode_idx += 1
                    continue

                if key == "p":
                    snap_dir = DATASET_ROOT / "snapshots"
                    snap_dir.mkdir(parents=True, exist_ok=True)
                    snap_path = snap_dir / f"snapshot_{int(now)}.jpg"
                    ok = save_snapshot(cap, snap_path)
                    print(f"📸 snapshot {'saved' if ok else 'failed'} -> {snap_path}")
                    continue

                if key == "z":
                    print("回到初始位...")
                    current = get_obs(robot)
                    move_smooth(robot, current, start_pose, duration=2.0)
                    target = dict(start_pose)
                    active_joint_keys.clear()
                    print("已回初始位")
                    continue

                if key == "u":
                    print("执行抬升辅助...")
                    current = get_obs(robot)
                    lift_pose = dict(current)
                    lift_pose["shoulder_lift.pos"] = current["shoulder_lift.pos"] - 8.0
                    lift_pose["elbow_flex.pos"] = current["elbow_flex.pos"] - 6.0
                    lift_pose["wrist_flex.pos"] = current["wrist_flex.pos"] + 4.0
                    lift_pose = clamp_target(lift_pose)
                    move_smooth(robot, current, lift_pose, duration=1.0)
                    target = dict(lift_pose)
                    active_joint_keys.clear()
                    print("已抬升")
                    continue

                if key in JOINT_KEYS:
                    active_joint_keys[key] = now

            if now - last_control_ts >= control_period:
                active_joint_keys = {
                    k: ts for k, ts in active_joint_keys.items()
                    if now - ts <= ACTIVE_KEY_HOLD_SEC
                }

                if active_joint_keys:
                    delta_by_joint = {joint: 0.0 for joint in JOINT_ORDER}
                    for active_key in active_joint_keys:
                        joint_map = JOINT_KEYS[active_key]
                        for joint_name, direction in joint_map.items():
                            delta_by_joint[joint_name] += direction * step_size

                    for joint_name, delta in delta_by_joint.items():
                        if abs(delta) > 1e-6:
                            target[joint_name] += delta

                    target = clamp_target(target)
                    send_target(robot, target)

                if is_recording:
                    obs = get_obs(robot)
                    entry = {
                        "ts": now,
                        "observation": obs,
                        "target": dict(target),
                        "active_keys": sorted(active_joint_keys.keys()),
                    }
                    state_log.append(entry)
                    if cap is not None and frame_idx % SNAPSHOT_EVERY_N_FRAMES == 0:
                        img_path = record_img_dir / f"frame_{frame_idx:05d}.jpg"
                        save_snapshot(cap, img_path)
                    frame_idx += 1

                last_control_ts = now

            time.sleep(0.001)

    finally:
        if is_recording and record_ep_dir is not None:
            with open(record_ep_dir / "states.json", "w", encoding="utf-8") as f:
                json.dump(state_log, f, ensure_ascii=False, indent=2)
            with open(record_ep_dir / "meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "episode_idx": episode_idx,
                    "interrupted": True,
                    "frames_logged": frame_idx,
                    "states_logged": len(state_log),
                    "camera_enabled": cap is not None,
                }, f, ensure_ascii=False, indent=2)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        if cap is not None:
            cap.release()
        try:
            robot.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
