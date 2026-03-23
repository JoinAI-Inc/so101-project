import os
import cv2
import time
import json
import threading
from lerobot.robots.so_follower.so_follower import SOFollower

print("🎬 [Join AI] SO-101 防堵塞多线程物理示教录制系统启动...")

# ==========================================
# 1. 唤醒躯干与视觉
# ==========================================
config = SOFollower.config_class(port="/dev/ttyACM0", id="my_awesome_follower_arm")
arm = SOFollower(config)
arm.connect()

cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

motor_names = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]

# ==========================================
# 2. 混合扭矩模式
# ==========================================
print("🔧 正在配置混合扭矩模式...")
for name in motor_names[:5]:
    arm.bus.write("Torque_Enable", name, 0) # 前5个关节变软允许拖拽

arm.bus.write("Torque_Enable", "gripper", 1) # 夹爪锁死听指挥

# 👉 你的专属张开与夹紧密码
GRIPPER_OPEN = 100   
GRIPPER_CLOSE = 18  
is_gripper_closed = False
arm.bus.write("Goal_Position", "gripper", GRIPPER_OPEN)

# ==========================================
# 3. 状态变量初始化
# ==========================================
running = True
is_recording = False
episode_idx = 0
frames_buffer = []
states_buffer = []

# 🌟 核心补丁：指令信箱 (防止多线程串口撞车)
command_mailbox = None 

os.makedirs("dataset/images", exist_ok=True)
os.makedirs("dataset/states", exist_ok=True)

# ==========================================
# 4. 后台监听指令 (只负责收信，绝不碰硬件！)
# ==========================================
def command_listener():
    global running, command_mailbox
    print("\n🎮 操作说明 (在终端输入后按回车执行)：")
    print(" - [直接按回车]：切换夹爪 (张开/夹紧)")
    print(" - [输入 r 回车]：开始录制")
    print(" - [输入 s 回车]：保存数据")
    print(" - [输入 q 回车]：退出系统\n")
    
    while running:
        try:
            cmd = input().strip().lower()
            command_mailbox = cmd # 把指令扔进信箱就跑
        except EOFError:
            pass

listener_thread = threading.Thread(target=command_listener, daemon=True)
listener_thread.start()

# ==========================================
# 5. 主线程：独占串口的录制大循环
# ==========================================
try:
    while running:
        # 🌟 第一步：先看信箱里有没有操作指令？(所有串口操作都在这里排队)
        if command_mailbox is not None:
            cmd = command_mailbox
            command_mailbox = None # 阅后即焚，清空信箱
            
            if cmd == 'q':
                running = False
            elif cmd == 'r' and not is_recording:
                print(f"🎥 开始录制 Episode {episode_idx} ...")
                is_recording = True
                frames_buffer.clear()
                states_buffer.clear()
            elif cmd == 's' and is_recording:
                print(f"💾 正在保存 Episode {episode_idx} (共 {len(frames_buffer)} 帧)...")
                is_recording = False
                
                ep_img_dir = f"dataset/images/ep_{episode_idx}"
                os.makedirs(ep_img_dir, exist_ok=True)
                for i, f in enumerate(frames_buffer):
                    cv2.imwrite(f"{ep_img_dir}/frame_{i:04d}.jpg", f)
                
                with open(f"dataset/states/ep_{episode_idx}.json", "w") as f:
                    json.dump(states_buffer, f)
                
                print(f"✅ Episode {episode_idx} 保存成功！")
                episode_idx += 1
            elif cmd == '': # 如果什么都没输入直接回车，就切换夹爪
                is_gripper_closed = not is_gripper_closed
                target = GRIPPER_CLOSE if is_gripper_closed else GRIPPER_OPEN
                arm.bus.write("Goal_Position", "gripper", target)
                print(f"🤌 夹爪已动作: {'夹紧 (18)' if is_gripper_closed else '张开 (100)'}")

        # 🌟 第二步：读取画面
        ret, frame = cap.read()
        if not ret: continue

        if int(time.time() * 10) % 3 == 0: 
            display = frame.copy()
            status = "RECORDING" if is_recording else "READY"
            color = (0, 0, 255) if is_recording else (0, 255, 0)
            cv2.putText(display, f"Status: {status} | EP: {episode_idx}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.imwrite("/home/node/.openclaw/workspace_DD/current_view.jpg", display)

        # 🌟 第三步：读取串口并录制
        if is_recording:
            current_positions = [arm.bus.read("Present_Position", name) for name in motor_names]
            frames_buffer.append(frame)
            states_buffer.append(current_positions)
            time.sleep(0.03)

except KeyboardInterrupt:
    running = False
finally:
    arm.bus.write("Torque_Enable", "gripper", 0)
    cap.release()
    arm.disconnect()
    print("\n🔌 数据采集系统已安全关闭。")
