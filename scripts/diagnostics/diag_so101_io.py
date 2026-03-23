#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import importlib
import inspect
import numpy as np


def build_robot(port="/dev/ttyACM0", robot_id="my_awesome_follower_arm"):
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
            if robot is not None:
                return robot
        except Exception:
            pass
    raise RuntimeError("cannot build robot")


def connect_skip_calib(robot):
    sig = inspect.signature(robot.connect)
    if "calibrate" in sig.parameters:
        return robot.connect(calibrate=False)
    if hasattr(robot, "calibrate"):
        old = robot.calibrate
        robot.calibrate = lambda *a, **k: None
        try:
            return robot.connect()
        finally:
            robot.calibrate = old
    return robot.connect()


def get_obs(robot):
    for n in ("get_observation", "observe", "capture_observation"):
        if hasattr(robot, n):
            try:
                v = getattr(robot, n)()
                if isinstance(v, dict):
                    return v
            except Exception as e:
                return {"_err": repr(e)}
    return {"_err": "no_obs_method"}


def send(robot, vec, keys):
    p1 = {k: float(v) for k, v in zip(keys, vec)}
    p2 = {k.replace(".pos", ""): float(v) for k, v in zip(keys, vec)}
    for p in (p1, p2, {"main": p1}, {"main": p2}):
        try:
            robot.send_action(p)
            return True, p
        except Exception:
            pass
    return False, None


def main():
    robot = build_robot()
    connect_skip_calib(robot)

    keys = None
    if hasattr(robot, "action_features") and isinstance(robot.action_features, dict):
        keys = list(robot.action_features.keys())[:6]
    if not keys:
        keys = [f"joint_{i+1}.pos" for i in range(6)]

    print("action_keys:", keys)

    print("\n[1] read observation x5")
    for i in range(5):
        o = get_obs(robot)
        print(i, o.keys() if isinstance(o, dict) else type(o), o.get("_err") if isinstance(o, dict) else "")
        if isinstance(o, dict):
            st = o.get("observation.state", o.get("state"))
            print(" state:", st)
        time.sleep(0.2)

    # 从状态或中位生成基准命令
    base = np.array([0, 0, 0, 0, 0, 50], dtype=np.float32)
    o = get_obs(robot)
    if isinstance(o, dict):
        st = o.get("observation.state", o.get("state"))
        if st is not None:
            try:
                base = np.array(st, dtype=np.float32).reshape(-1)[:6]
            except Exception:
                pass

    print("\nbase cmd:", base)

    print("\n[2] send +10 on joint1, hold 1s, send back")
    cmd1 = base.copy()
    cmd1[0] = np.clip(cmd1[0] + 10.0, -100, 100)
    ok, payload = send(robot, cmd1, keys)
    print("send1 ok:", ok, "payload_sample:", payload)
    time.sleep(1.0)

    o1 = get_obs(robot)
    print("obs after send1:", o1.get("observation.state", o1.get("state")) if isinstance(o1, dict) else o1, o1.get("_err") if isinstance(o1, dict) else "")

    ok, payload = send(robot, base, keys)
    print("send2(back) ok:", ok)
    time.sleep(1.0)

    o2 = get_obs(robot)
    print("obs after back:", o2.get("observation.state", o2.get("state")) if isinstance(o2, dict) else o2, o2.get("_err") if isinstance(o2, dict) else "")

    # 尝试断开
    try:
        if hasattr(robot, "disconnect"):
            robot.disconnect()
        elif hasattr(robot, "close"):
            robot.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
