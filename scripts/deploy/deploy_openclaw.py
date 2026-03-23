#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import importlib
import inspect
import os
import time
import urllib.request

import cv2
import numpy as np
import torch
from lerobot.policies.diffusion.modeling_diffusion import DiffusionPolicy


class FoolproofCamera:
    def __init__(self, url: str, timeout: float = 3.0):
        self.url = url
        self.timeout = timeout

    def read(self):
        try:
            req = urllib.request.Request(
                self.url,
                headers={"User-Agent": "Mozilla/5.0", "Connection": "close"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = getattr(resp, "status", 200)
                ctype = resp.headers.get("Content-Type", "")
                data = resp.read()

            if status != 200 or "image" not in ctype.lower() or len(data) < 100:
                return False, None

            frame = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            return (frame is not None), frame
        except Exception:
            return False, None

    def release(self):
        pass


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
        except Exception:
            pass

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
            except Exception:
                pass
    return {}


def extract_state(obs, default_dim=6):
    if not isinstance(obs, dict):
        return [0.0] * default_dim

    for k in ("observation.state", "state", "observation.joints", "joints"):
        if k in obs:
            v = obs[k]
            if isinstance(v, torch.Tensor):
                v = v.detach().cpu().numpy()
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


def to_image_tensor(frame_bgr, device):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    t = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0
    return t.unsqueeze(0).to(device)


def flatten_action(x):
    if isinstance(x, torch.Tensor):
        arr = x.detach().cpu().float().numpy()
    else:
        arr = np.asarray(x, dtype=np.float32)
    arr = np.squeeze(arr)
    if arr.ndim == 2:
        arr = arr[0]
    if arr.ndim != 1:
        raise ValueError(f"Unexpected action shape: {arr.shape}")
    return arr.astype(np.float32)


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
    variants = [p1, p2, {"main": p1}, {"main": p2}]

    last_err = None
    for p in variants:
        try:
            robot.send_action(p)
            return
        except Exception as e:
            last_err = e
    raise RuntimeError(f"send_action failed: {repr(last_err)}")


def clamp_sofollower(cmd):
    cmd = cmd.copy()
    if len(cmd) >= 5:
        cmd[:5] = np.clip(cmd[:5], -100.0, 100.0)
    if len(cmd) >= 6:
        cmd[5] = np.clip(cmd[5], 0.0, 100.0)
    return cmd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy_dir", required=True)
    ap.add_argument("--robot_port", default="/dev/ttyACM0")
    ap.add_argument("--robot_id", default="my_awesome_follower_arm")
    ap.add_argument("--camera_url", required=True)
    ap.add_argument("--task", default="pick up the orange")
    ap.add_argument("--rate_hz", type=float, default=5.0)
    ap.add_argument("--camera_timeout", type=float, default=3.0)

    ap.add_argument("--action_scale", type=float, default=0.7)
    ap.add_argument("--action_clip", type=float, default=1.0)
    ap.add_argument("--deadband", type=float, default=0.2)
    ap.add_argument("--max_step", type=float, default=0.45)
    ap.add_argument("--anchor_alpha", type=float, default=0.03)

    ap.add_argument("--display", action="store_true")
    ap.add_argument("--skip_calibration", action="store_true", default=True)
    ap.add_argument("--self_test", action="store_true", default=True)
    ap.add_argument("--verbose", action="store_true", default=True)
    args = ap.parse_args()

    if not args.display:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🧠 Loading policy: {args.policy_dir}")
    policy = DiffusionPolicy.from_pretrained(args.policy_dir)
    policy.eval().to(device)
    print(f"✅ Policy ready on {device}")

    robot = build_so_robot(args.robot_port, args.robot_id)
    connect_robot(robot, skip_calibration=args.skip_calibration)
    print("✅ Robot connected")

    cam = FoolproofCamera(args.camera_url, timeout=args.camera_timeout)
    print("👀 Camera ready")

    obs0 = get_robot_observation(robot)
    joints0 = np.array(extract_state(obs0, default_dim=6), dtype=np.float32)
    if np.allclose(joints0, 0.0):
        joints0 = np.array([0.0, 0.0, 0.0, 6.0, -18.0, 2.0], dtype=np.float32)

    action_keys = infer_action_keys(robot, len(joints0))
    print(f"ℹ️ action_keys={action_keys}")

    if args.self_test:
        print("🧪 Self-test: shoulder_pan +6 -> back")
        tmp = joints0.copy()
        tmp[0] = np.clip(tmp[0] + 6.0, -100.0, 100.0)
        send_action_dict(robot, tmp, action_keys)
        time.sleep(0.6)
        send_action_dict(robot, joints0, action_keys)
        time.sleep(0.6)

    period = 1.0 / max(args.rate_hz, 1.0)
    show_ok = args.display
    task_warned = False
    print("🚀 Running deploy loop. Ctrl+C stop.")

    try:
        with torch.inference_mode():
            while True:
                t0 = time.time()

                ok, frame = cam.read()
                if not ok:
                    time.sleep(0.02)
                    continue

                obs = get_robot_observation(robot)
                raw = np.array(extract_state(obs, default_dim=6), dtype=np.float32)
                joints = raw if not np.allclose(raw, 0.0) else joints0.copy()

                observation = {
                    "observation.images.base_0_rgb": to_image_tensor(frame, device),
                    "observation.state": torch.tensor(joints, dtype=torch.float32, device=device).unsqueeze(0),
                    "task": args.task,
                    "language_instruction": args.task,
                }

                try:
                    pred = policy.select_action(observation, task=args.task)
                except TypeError:
                    if not task_warned:
                        print("\n⚠️ 当前 DiffusionPolicy 不支持 task 参数，使用 observation 内文本字段")
                        task_warned = True
                    pred = policy.select_action(observation)

                delta = flatten_action(pred)
                delta = np.clip(delta * args.action_scale, -args.action_clip, args.action_clip)

                # freeze wrist+gripper for stability
                delta[3] = 0.0
                delta[4] = 0.0
                delta[5] = 0.0

                # suppress downward drift on joint 2
                if delta[1] < 0:
                    delta[1] *= 0.35

                delta[np.abs(delta) < args.deadband] = 0.0
                delta = np.clip(delta, -args.max_step, args.max_step)

                # small pull back to start pose
                delta += args.anchor_alpha * (joints0 - joints)

                cmd = joints + delta
                cmd = clamp_sofollower(cmd)

                # workspace guardrails
                cmd[1] = np.clip(cmd[1], -5.0, 26.0)    # shoulder_lift
                cmd[2] = np.clip(cmd[2], -5.0, 24.0)    # elbow_flex
                cmd[3] = np.clip(cmd[3], 4.5, 8.0)      # wrist_flex fixed band
                cmd[4] = np.clip(cmd[4], -22.0, -17.0)  # wrist_roll fixed band
                cmd[5] = np.clip(cmd[5], 0.0, 5.0)      # gripper mostly open

                send_action_dict(robot, cmd, action_keys)

                if args.verbose:
                    hz = 1.0 / max(time.time() - t0, 1e-6)
                    print(
                        f"\rHz={hz:5.2f} | raw={np.round(raw,2)} | delta={np.round(delta,2)} | cmd={np.round(cmd,2)}",
                        end="",
                        flush=True,
                    )

                if show_ok:
                    try:
                        cv2.imshow("SO Deploy", frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            print("\n🛑 Stop by key 'q'")
                            break
                    except cv2.error:
                        print("\n⚠️ OpenCV GUI unavailable, display disabled")
                        show_ok = False

                sleep_s = period - (time.time() - t0)
                if sleep_s > 0:
                    time.sleep(sleep_s)

    except KeyboardInterrupt:
        print("\n🛑 Stop by Ctrl+C")
    finally:
        try:
            cam.release()
        except Exception:
            pass
        if show_ok:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        try:
            if hasattr(robot, "disconnect"):
                robot.disconnect()
            elif hasattr(robot, "close"):
                robot.close()
        except Exception:
            pass
        print("\n✅ Clean shutdown")


if __name__ == "__main__":
    main()
