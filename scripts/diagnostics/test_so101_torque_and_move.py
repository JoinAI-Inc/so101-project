#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib
import inspect
import time
import numpy as np


def build_so_robot(port: str, robot_id: str):
    robots_mod = importlib.import_module('lerobot.robots')
    so_mod = importlib.import_module('lerobot.robots.so_follower')
    make_robot_from_config = robots_mod.make_robot_from_config
    for cfg_name in ('SO101FollowerConfig', 'SO100FollowerConfig', 'SOFollowerRobotConfig'):
        if not hasattr(so_mod, cfg_name):
            continue
        cfg_cls = getattr(so_mod, cfg_name)
        try:
            sig = inspect.signature(cfg_cls)
            kwargs = {}
            if 'type' in sig.parameters:
                kwargs['type'] = 'so_follower'
            if 'port' in sig.parameters:
                kwargs['port'] = port
            if 'id' in sig.parameters:
                kwargs['id'] = robot_id
            if 'cameras' in sig.parameters:
                kwargs['cameras'] = {}
            if 'follower_arms' in sig.parameters:
                kwargs['follower_arms'] = {'main': port}
            cfg = cfg_cls(**kwargs)
            if not hasattr(cfg, 'type'):
                setattr(cfg, 'type', 'so_follower')
            robot = make_robot_from_config(cfg)
            if robot is not None and hasattr(robot, 'send_action'):
                print(f'✅ Robot created via config: {cfg_name}')
                return robot
        except Exception as e:
            print('skip', cfg_name, repr(e))
    raise RuntimeError('无法构建 SOFollower 机器人')


def connect_robot(robot):
    sig = inspect.signature(robot.connect)
    if 'calibrate' in sig.parameters:
        print('ℹ️ connect with calibrate=False')
        return robot.connect(calibrate=False)
    return robot.connect()


def obs(robot):
    d = robot.get_observation()
    ks = ['shoulder_pan.pos','shoulder_lift.pos','elbow_flex.pos','wrist_flex.pos','wrist_roll.pos','gripper.pos']
    return np.array([float(d[k]) for k in ks], dtype=np.float32)


def main():
    robot = build_so_robot('/dev/ttyACM0', 'my_awesome_follower_arm')
    connect_robot(robot)
    motors = ['shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll','gripper']

    print('initial', np.round(obs(robot), 3))
    for m in motors:
        try:
            val = robot.bus.read('Torque_Enable', m)
            print(f'before torque {m}:', val)
        except Exception as e:
            print(f'before torque {m}: read failed {e!r}')

    for m in motors:
        robot.bus.write('Torque_Enable', m, 1)
    time.sleep(0.2)

    for m in motors:
        try:
            val = robot.bus.read('Torque_Enable', m)
            print(f'after torque {m}:', val)
        except Exception as e:
            print(f'after torque {m}: read failed {e!r}')

    start = obs(robot)
    cmd = start.copy()
    cmd[0] += 20.0
    payload = {
        'shoulder_pan.pos': float(cmd[0]),
        'shoulder_lift.pos': float(cmd[1]),
        'elbow_flex.pos': float(cmd[2]),
        'wrist_flex.pos': float(cmd[3]),
        'wrist_roll.pos': float(cmd[4]),
        'gripper.pos': float(cmd[5]),
    }
    print('send cmd', payload)
    sent = robot.send_action(payload)
    print('sent', sent)
    time.sleep(2.0)
    mid = obs(robot)
    print('mid', np.round(mid, 3))
    robot.send_action({
        'shoulder_pan.pos': float(start[0]),
        'shoulder_lift.pos': float(start[1]),
        'elbow_flex.pos': float(start[2]),
        'wrist_flex.pos': float(start[3]),
        'wrist_roll.pos': float(start[4]),
        'gripper.pos': float(start[5]),
    })
    time.sleep(1.0)
    end = obs(robot)
    print('end', np.round(end, 3))
    robot.disconnect()


if __name__ == '__main__':
    main()
