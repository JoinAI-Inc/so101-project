#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import importlib
import inspect
import time

import numpy as np


def build_so_robot(port: str, robot_id: str):
    robots_mod = importlib.import_module("lerobot.robots")
    so_mod = importlib.import_module("lerobot.robots.so_follower")
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

    raise RuntimeError("无法构建 SOFollower 机器人")


def connect_robot(robot, skip_calibration=True):
    if not skip_calibration:
        return robot.connect()

    sig = inspect.signature(robot.connect)
    for k in ("calibrate", "run_calibration", "do_calibration", "perform_calibration"):
        if k in sig.parameters:
            print(f"ℹ️ connect with {k}=False (skip calibration)")
            return robot.connect(**{k: False})

    if hasattr(robot, "calibrate"):
        old = robot.calibrate
        robot.calibrate = lambda *a, **kw: None
        try:
            return robot.connect()
        finally:
            robot.calibrate = old

    return robot.connect()


def get_robot_observation(robot):
    for n in ("get_observation", "observe", "capture_observation"):
        if hasattr(robot, n):
            try:
                v = getattr(robot, n)()
                if isinstance(v, dict):
                    return v
            except Exception as e:
                print(f"obs via {n} failed: {e!r}")
    return {}


def extract_state(obs, default_dim=6):
    if not isinstance(obs, dict):
        return [0.0] * default_dim

    for k in ("observation.state", "state", "observation.joints", "joints"):
        if k in obs:
            v = obs[k]
            try:
                import torch
                if isinstance(v, torch.Tensor):
                    v = v.detach().cpu().numpy()
            except Exception:
                pass
            if isinstance(v, np.ndarray):
                v = v.squeeze().tolist()
            if isinstance(v, (list, tuple)) and len(v) > 0:
                return [float(x) for x in v]

    flat = [
        "shoulder_pan.pos",
        "shoulder_lift.pos",
        "elbow_flex.pos",
        "wrist_flex.pos",
        "wrist_roll.pos",
        "gripper.pos",
    ]
    if all(k in obs for k in flat):
        return [float(obs[k]) for k in flat]

    flat2 = [k.replace(".pos", "") for k in flat]
    if all(k in obs for k in flat2):
        return [float(obs[k]) for k in flat2]

    return [0.0] * default_dim


def infer_action_keys(robot, action_dim):
    if hasattr(robot, "action_features"):
        af = getattr(robot, "action_features")
        if isinstance(af, dict):
            ks = list(af.keys())
            if len(ks) >= action_dim:
                return ks[:action_dim]
    return [f"joint_{i+1}.pos" for i in range(action_dim)]


def send_action_dict(robot, cmd_vec, action_keys):
    p1 = {k: float(v) for k, v in zip(action_keys, cmd_vec)}
    p2 = {k.replace(".pos", ""): float(v) for k, v in zip(action_keys, cmd_vec)}
    variants = [
        ("plain.pos", p1),
        ("plain", p2),
        ("main.pos", {"main": p1}),
        ("main", {"main": p2}),
    ]

    last_err = None
    for name, payload in variants:
        try:
            robot.send_action(payload)
            print(f"✅ send_action variant worked: {name}")
            return name
        except Exception as e:
            last_err = e
            print(f"❌ send_action variant failed: {name} -> {e!r}")
    raise RuntimeError(f"send_action failed: {repr(last_err)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--robot_port", default="/dev/ttyACM0")
    ap.add_argument("--robot_id", default="my_awesome_follower_arm")
    ap.add_argument("--joint", type=int, default=0, help="0-based joint index")
    ap.add_argument("--delta", type=float, default=6.0)
    ap.add_argument("--hold", type=float, default=1.0)
    ap.add_argument("--skip_calibration", action="store_true", default=True)
    args = ap.parse_args()

    robot = build_so_robot(args.robot_port, args.robot_id)
    connect_robot(robot, skip_calibration=args.skip_calibration)
    print("✅ Robot connected")

    obs0 = get_robot_observation(robot)
    print("ℹ️ observation keys:", sorted(list(obs0.keys()))[:30])
    joints0 = np.array(extract_state(obs0, default_dim=6), dtype=np.float32)
    print("ℹ️ initial joints:", np.round(joints0, 3))

    action_keys = infer_action_keys(robot, len(joints0))
    print("ℹ️ action_keys:", action_keys)

    cmd = joints0.copy()
    cmd[args.joint] = cmd[args.joint] + args.delta
    print("ℹ️ test cmd:", np.round(cmd, 3))

    used = send_action_dict(robot, cmd, action_keys)
    print(f"ℹ️ moving joint {args.joint} by +{args.delta} for {args.hold}s using {used}")
    time.sleep(args.hold)

    send_action_dict(robot, joints0, action_keys)
    print("ℹ️ returned to initial joints")
    time.sleep(0.5)

    obs1 = get_robot_observation(robot)
    joints1 = np.array(extract_state(obs1, default_dim=6), dtype=np.float32)
    print("ℹ️ final joints:", np.round(joints1, 3))

    try:
        if hasattr(robot, "disconnect"):
            robot.disconnect()
        elif hasattr(robot, "close"):
            robot.close()
    except Exception:
        pass
    print("✅ Done")


if __name__ == "__main__":
    main()
