# Runs only on Raspberry Pi

from picamera2 import Picamera2
import cv2
import socket
import time
from enum import Enum
import os
import config
from streamer import FrameTCPStreamer
from process_frame import process_frame, Direction
import visualization
from collections import deque
import find_boundries as fb

class Action(Enum):
    LEFT = 'V'
    RIGHT = 'H'
    STOP_NA = 'S'
    STOP = 'B'

SOCKET_PATH = "/tmp/cam_offset.sock"
JPEG_QUALITY = 60
SOCKET_PATH_CPP_TO_PY = "/tmp/cpp_to_py.sock"

picam2 = Picamera2()
streamer = FrameTCPStreamer(host="0.0.0.0", port=config.PORT)
_udps = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
_rx_sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
_rx_sock.setblocking(False)

try:
    os.unlink(SOCKET_PATH_CPP_TO_PY)
except FileNotFoundError:
    pass
_rx_sock.bind(SOCKET_PATH_CPP_TO_PY)

def picam_init():
    cam_cfg = picam2.create_preview_configuration(
        main={"format": "RGB888", "size": (config.FRAME_W, config.FRAME_H)}
    )
    picam2.configure(cam_cfg)
    picam2.start()

def streamer_init():
    streamer.start()

def capture_frame():
    frame = picam2.capture_array()
    return frame

def quantize_heading_to_7bit(heading_deg: float, v_min=-25.0, v_max=25.0) -> int:
    """
    Map heading angle in degrees to a 7-bit integer (0..127).
    """
    clamped = max(v_min, min(v_max, heading_deg))
    norm = (clamped - v_min) / (v_max - v_min)
    return int(round(norm * 127)) & 0x7F  # 0..127

def send_heading(heading_deg: float):
    q = quantize_heading_to_7bit(heading_deg)
    try:
        _udps.sendto(bytes([q]), SOCKET_PATH)
    except FileNotFoundError:
        pass
    except Exception:
        pass

def send_image(frame):
    if streamer.has_client():
        ok, jpg = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
        )
        if ok:
            streamer.push_jpeg(jpg.tobytes())

def recv_uint8_array():
    data, _ = _rx_sock.recvfrom(1 + 255)

    if not data or len(data) < 1: return []

    count = data[0]
    available = len(data) - 1
    if count > available:
        count = available

    if count == 0: return []

    vals = list(data[1:1 + count])
    return vals


def send_stop(is_last = False):
    code = 0xFE if is_last else 0xFF
    try:
        _udps.sendto(bytes([code]), SOCKET_PATH)
        print("Sent stop command:", code)
    except Exception as e:
        print("Could not send stop command")
        print(e)

def main():
    picam_init()
    streamer_init()

    print("Camera + streamer running. Press Ctrl+C to exit.")
    fps_t0 = time.time()
    frame_count = 0
    vals = []

    intersection_is_active = False

    dir = Direction.LEFT
    next_action: Action = Action.STOP_NA
    action_completed = True
    intersection_cntr = deque([False] * config.BUFFER_LENGTH, maxlen=config.BUFFER_LENGTH)
    stopline_cntr = deque([False] * config.BUFFER_LENGTH, maxlen=config.BUFFER_LENGTH)
    normal_road_cntr = deque([False] * config.BUFFER_LENGTH, maxlen=config.BUFFER_LENGTH)
    stop_section_active = False
    waiting_for_route = False
    last_stop = False

    try:
        while True:
            frame = capture_frame()

            try:
                new_vals = recv_uint8_array()
                if new_vals:
                    vals = new_vals
                    print("Ny rutt: ", vals)
                    action_completed = True
                    last_stop = False
            except BlockingIOError:
                pass
            
            if action_completed:
                if vals:
                    waiting_for_route = False
                    try:
                        cmd = vals.pop(0)
                        next_action = Action(chr(cmd))
                        print("Nästa kommando:", chr(cmd))
                        if next_action == Action.LEFT:
                            dir = Direction.LEFT
                        elif next_action == Action.RIGHT:
                            dir = Direction.RIGHT
                        
                        action_completed = False
                        if not vals:
                            last_stop = True
                    except ValueError:
                        print("Recieved invalid byte:", cmd)
                        continue
                else:
                    if not waiting_for_route:
                        print("Inväntar ny rutt...")
                        waiting_for_route = True

                    send_image(frame)
                    send_heading(0.0)
                    time.sleep(0.05)
                    continue

            # Run vision processing pipeline
            res = process_frame(frame, dir, force_dir=intersection_is_active)
            intersection_cntr.append(res.other_path is not None)
            
            stopline_cntr.append(res.stop_point is not None)
            
            is_normal = res.both_edges_found and res.other_path is None
            normal_road_cntr.append(is_normal)

            # Check intersection
            next_is_turn = (next_action == Action.LEFT or next_action == Action.RIGHT)
            if intersection_cntr.count(True) >= config.INTO_THRESHOLD and not intersection_is_active and next_is_turn:
                intersection_is_active = True
                if dir == Direction.LEFT:
                    print("Håller till vänster i korsning...")
                elif dir == Direction.RIGHT:
                    print("Håller till höger i korsning...")
            elif normal_road_cntr.count(True) >= config.EXIT_THRESHOLD and intersection_is_active:
                if res.median_lane_width and res.median_lane_width < 0.67:
                    intersection_is_active = False
                    action_completed = True
                    print("Ute ur korsning.")
            
            # Check stopline
            if stopline_cntr.count(True) >= config.INTO_THRESHOLD and not stop_section_active and not intersection_is_active:
                stop_section_active = True
                if next_action == Action.STOP and res.dist_to_stopline is not None:
                    print("Hittade hållplats")   
                    send_stop(last_stop)
                else:
                    print("Passerar stopplinje...")

            elif stopline_cntr.count(False) >= config.EXIT_THRESHOLD and stop_section_active:
                stop_section_active = False
                action_completed = True

                if next_action == Action.STOP:
                    print("Lämnar hållplats.")
                else:
                    print("Stoplinje passerad.")
            
            # Send 7-bit heading
            if intersection_is_active:
                res.heading *= config.INTERSECTION_HEADING_MULTIPLIER
            send_heading(res.heading)
            send_image(visualization.build(frame, res, intersection_is_active))
        
            frame_count += 1
            if config.PERFORMANCE_LOGGING:
                if frame_count == 1:
                    fps_t0 = time.time()

                if frame_count >= 100:
                    now = time.time()
                    elapsed = now - fps_t0
                    fps = frame_count / elapsed
                    print(f"FPS: {fps:.1f}")

                    # reset for next batch
                    fps_t0 = now
                    frame_count = 0
                

    except KeyboardInterrupt:
        print("Exiting...")
        send_stop(is_last=True)

    finally:
        try:
            picam2.stop()
        except Exception:
            pass
        streamer.stop()
        _udps.close()
        print("Exited.")

if __name__ == "__main__":
    main()
