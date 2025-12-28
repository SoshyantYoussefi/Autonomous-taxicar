import socket
import threading
import sys
import json
import time
import tkinter as tk
from tkinter import ttk

# === [NYTT] För video-dekod & protokoll ===
import struct
import io
try:
    from PIL import Image, ImageTk
except ImportError:
    raise SystemExit("Installera Pillow först:  pip install pillow")


#----------- MOVE DATA --------------#

#JSON_PATH = "/code/common/move_data.json"

with open("move_data.json", "r", encoding="utf-8") as f:
    OPCODES = json.load(f)["move_data"]

# === OPCODES (matchar din C-enum) ===
MOVE_COMMAND       = 0x01
VAXLING            = 0x02

OFFSET_ANGLE       = 0x10

OPCODE_SET_PID_P   = 0x11
OPCODE_SET_PID_I   = 0x12
OPCODE_SET_PID_D   = 0x20

OPCODE_HALL        = 0x03
OPCODE_CALIB_HALL  = 0x30
OPCODE_ULTRASONIC  = 0x04

# används för rörelsekommandon: [MOVE_COMMAND][DATA_BYTE]
move_opcode = MOVE_COMMAND


# === Network / Connection ===

PI_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.42"
PORT  = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
s.connect((PI_IP, PORT))

# [NYTT] Video-port + socket (andra TCP-anslutningen)
VIDEO_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 6000
vsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
vsock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
try:
    vsock.connect((PI_IP, VIDEO_PORT))
    video_connected = True
except OSError as e:
    print(f"[Video] kunde inte ansluta till {PI_IP}:{VIDEO_PORT}: {e}")
    video_connected = False
    vsock = None

# === Root Window Setup ===

root = tk.Tk()
root.title("Max Verstappen Controller (Online)")
root.geometry("1000x720")
root.minsize(1000, 720)

# === Color Scheme ===
bg_dark       = "#1e1e1e"
card_bg       = "#2b2b2b"
button_bg     = "#3a3a3a"
button_hover  = "#5a5a5a"
button_active = "#777777"
text_light    = "#f5f5f5"
accent        = "#aaaaaa"

root.configure(bg=bg_dark)

# === ttk Style ===
style = ttk.Style()
style.theme_use("default")
style.configure(".", background=bg_dark, foreground=text_light)
style.configure("Card.TLabel", background=card_bg, foreground=text_light, font=("Consolas", 11))

# === Helper: Card Container with Title ===
def create_card(parent, title: str):
    wrapper = tk.Frame(parent, bg=bg_dark)
    wrapper.pack(fill="x", padx=15, pady=(12, 6))

    tk.Label(
        wrapper,
        text=title,
        font=("Consolas", 11, "bold"),
        fg=text_light,
        bg=bg_dark,
        anchor="w",
    ).pack(anchor="w", pady=(0, 4), padx=(5, 0))

    card = tk.Frame(wrapper, bg=card_bg, bd=0, relief="flat", highlightthickness=0)
    card.pack(fill="x", expand=True, ipady=8, ipadx=8)
    return card

# === Layout ===
root.columnconfigure(0, weight=2)
root.columnconfigure(1, weight=1)

main_frame = tk.Frame(root, bg=bg_dark)
main_frame.grid(row=0, column=0, sticky="nsew")

side_frame = tk.Frame(root, bg=bg_dark)
side_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 15))

# === Tk Variables ===
volt_v        = tk.StringVar(value="--.--")
seq_v         = tk.StringVar(value="--")
speed_kmh_v   = tk.StringVar(value="--")
ultrasound_v  = tk.StringVar(value="--")
odometer_v    = tk.StringVar(value="--")
logs_v        = tk.StringVar(value="")
ultra_max     = tk.StringVar(value="300")

# internal odometer estimate (from speed)
odo_value = 0.0

# === Telemetry Card ===
tele_card = create_card(main_frame, "Telemetry")

def tele_label(row, text, var):
    tk.Label(
        tele_card,
        text=text,
        font=("Consolas", 11),
        bg=card_bg,
        fg=text_light,
    ).grid(row=row, column=0, sticky="w", padx=10, pady=4)
    tk.Label(
        tele_card,
        textvariable=var,
        font=("Consolas", 11),
        bg=card_bg,
        fg=accent,
    ).grid(row=row, column=1, sticky="w")

tele_label(0, "Battery (V):",   volt_v)
tele_label(1, "seq:",           seq_v)
tele_label(2, "Speed (km/h):",  speed_kmh_v)

# === Sensors Card ===
sensor_card = create_card(main_frame, "Sensors")

def sensor_label(row, text, var):
    tk.Label(
        sensor_card,
        text=text,
        font=("Consolas", 11),
        bg=card_bg,
        fg=text_light,
    ).grid(row=row, column=0, sticky="w", padx=10, pady=4)
    tk.Label(
        sensor_card,
        textvariable=var,
        font=("Consolas", 11),
        bg=card_bg,
        fg=accent,
    ).grid(row=row, column=1, sticky="w")

sensor_label(0, "Ultrasound (cm):", ultrasound_v)
sensor_label(1, "Odometer (m):",    odometer_v)

# === Logs Card ===
logs_card = create_card(main_frame, "Logs")
tk.Label(
    logs_card,
    textvariable=logs_v,
    justify="left",
    bg=card_bg,
    fg=accent,
    font=("Consolas", 10),
).pack(anchor="w", padx=10, pady=5)

def append_log(msg: str):
    current = logs_v.get().splitlines()
    current.append(f"> {msg}")
    logs_v.set("\n".join(current[-8:]))

# === Controls Card ===
controls_card = create_card(main_frame, "Controls")

# --- Network send helpers ---

def send(cmd: str):
    """
    Movement packet:
        [MOVE_COMMAND][DATA_BYTE]

    DATA_BYTE tas från move_data.json via OPCODES dict.
    """
    if cmd not in OPCODES:
        append_log(f"Unknown command: {cmd}")
        return

    fixed_opcode = move_opcode           # 0x01 = MOVE_COMMAND
    data_byte = OPCODES[cmd]

    packet = bytes([fixed_opcode, data_byte])

    try:
        s.sendall(packet)
        append_log(f"Sent: 0x{fixed_opcode:02X} 0x{data_byte:02X} ({cmd})")
        print(f"Sent raw hex: {packet.hex()}  |  cmd={cmd}")
    except OSError as e:
        append_log(f"Send error: {e}")


def send_opcode(opcode: int, payload: bytes = b""):
    """
    Generic opcode packet:
        [OPCODE][PAYLOAD...]

    OPCODE är 1 byte (matchar din C-enum).
    Exempel:
        send_opcode(OPCODE_SET_PID_P, bytes([värde]))
    """
    opcode_byte = opcode & 0xFF
    pkt = bytes([opcode_byte]) + payload
    try:
        s.sendall(pkt)
        if payload:
            append_log(f"Sent OPCODE 0x{opcode_byte:02X}, payload={payload.hex()}")
        else:
            append_log(f"Sent OPCODE 0x{opcode_byte:02X} (no payload)")
        print(f"Sent raw opcode packet: {pkt.hex()}")
    except OSError as e:
        append_log(f"Send opcode error: {e}")

# === Mode Toggle (local-only for now) ===
mode_state = tk.StringVar(value="Manual")

def set_mode(mode):
    mode_state.set(mode)
    append_log(f"Mode set to {mode}")
    # Här kan du senare lägga t.ex:
    # send_opcode(VAXLING, bytes([0x01]))  osv.

def make_toggle(text, mode, column):
    def on_click():
        set_mode(mode)

    b = tk.Label(
        controls_card,
        text=text,
        bg=button_bg,
        fg=text_light,
        font=("Consolas", 10),
        width=12,
        height=2,
        relief="flat",
        cursor="hand2",
    )
    b.grid(row=0, column=column, padx=6, pady=(4, 10), sticky="nsew")

    def update_bg(*_):
        b.config(bg=button_hover if mode_state.get() == mode else button_bg)

    mode_state.trace_add("write", update_bg)
    b.bind("<Enter>", lambda e: b.config(bg=button_hover))
    b.bind("<Leave>", lambda e: update_bg())
    b.bind("<Button-1>", lambda e: on_click())
    update_bg()

make_toggle("Manual",      "Manual",      0)
make_toggle("Autonomous",  "Autonomous",  2)

# === Movement Buttons ===
active_buttons = {}

def make_button(text, cmd_down, cmd_up, r, c, key=None):
    """
    cmd_down / cmd_up är kommandosträngar som går till Pi,
    t.ex. "forward_down", "forward_up".
    """
    b = tk.Label(
        controls_card,
        text=text,
        bg=button_bg,
        fg=text_light,
        font=("Consolas", 10),
        width=12,
        height=2,
        relief="flat",
        cursor="hand2",
    )
    b.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

    def press():
        b.config(bg=button_active)
        if cmd_down:
            send(cmd_down)

    def release():
        b.config(bg=button_bg)
        if cmd_up:
            send(cmd_up)

    b.bind(
        "<Enter>",
        lambda e: b.config(
            bg=button_hover if b["bg"] != button_active else button_active
        ),
    )
    b.bind(
        "<Leave>",
        lambda e: b.config(
            bg=button_bg if b["bg"] != button_active else button_active
        ),
    )
    b.bind("<Button-1>",         lambda e: press())
    b.bind("<ButtonRelease-1>",  lambda e: release())

    if key:
        active_buttons[key] = (b, press, release)

# Map GUI buttons -> JSON movement command names
make_button("↑ Forward",   "forward_down",   "forward_up",   1, 1, "Up")
make_button("← Left",      "left_down",      "left_up",      2, 0, "Left")
make_button("Stop",        "stop_down",      "stop_up",      2, 1, "space")
make_button("Right →",     "right_down",     "right_up",     2, 2, "Right")
make_button("↓ Backward",  "backward_down",  "backward_up",  3, 1, "Down")

for i in range(3):
    controls_card.columnconfigure(i, weight=1)

# === Side Panel: Ultrasound Calibration ===
calib_card = create_card(side_frame, "Ultrasound Calibration")

tk.Label(
    calib_card,
    text="Max Distance (cm):",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).pack(anchor="w", pady=(0, 4), padx=10)

entry = tk.Entry(
    calib_card,
    textvariable=ultra_max,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=10,
    justify="center",
    font=("Consolas", 10),
)
entry.pack(anchor="w", padx=10, pady=(0, 6))

def apply_calibration():
    val = ultra_max.get()
    try:
        num = int(val)
        append_log(f"Applied ultrasound max distance: {num} cm")
        # här skulle du kunna skicka t.ex:
        # send_opcode(OPCODE_ULTRASONIC, num.to_bytes(1, 'big'))
    except ValueError:
        append_log("Invalid calibration value!")

apply_btn = tk.Label(
    calib_card,
    text="Apply",
    bg=button_bg,
    fg=text_light,
    font=("Consolas", 10),
    width=10,
    height=1,
    relief="flat",
    cursor="hand2",
)
apply_btn.pack(anchor="w", padx=10, pady=4)
apply_btn.bind("<Enter>", lambda e: apply_btn.config(bg=button_hover))
apply_btn.bind("<Leave>", lambda e: apply_btn.config(bg=button_bg))
apply_btn.bind("<Button-1>", lambda e: apply_calibration())

# Let Enter in the entry apply + unfocus
def on_apply_key(event=None):
    apply_calibration()
    root.focus()

entry.bind("<Return>", on_apply_key)

# Clicking outside the entry unfocuses it
def unfocus(event):
    if event.widget != entry:
        root.focus()

root.bind_all("<Button-1>", unfocus, add="+")

# === Camera Card ===
camera_card = create_card(side_frame, "Camera")

# [NYTT] Bildyta för kameraflöde
cam_label = tk.Label(
    camera_card,
    bg=card_bg,
    fg=accent,
    width=100,
    height=100,
    anchor="center",
    justify="center",
)
cam_label.pack(padx=10, pady=10)
_cam_img_ref = None  # behåll referens så bilden inte garbage-collectas
CAM_W, CAM_H = 480, 320  # visningsstorlek

if not video_connected:
    cam_label.config(text="[No camera feed]", fg=accent)

# === Keyboard Controls ===
pressed_keys = set()

def on_key_press(event):
    key = event.keysym
    if key in active_buttons and key not in pressed_keys:
        pressed_keys.add(key)
        btn, press, _ = active_buttons[key]
        btn.config(bg=button_active)
        press()

def on_key_release(event):
    key = event.keysym
    if key in pressed_keys and key in active_buttons:
        pressed_keys.remove(key)
        btn, _, release = active_buttons[key]
        btn.config(bg=button_bg)
        release()

root.bind_all("<KeyPress>", on_key_press)
root.bind_all("<KeyRelease>", on_key_release)

# === Telemetry handling ===

def interpret_ultrasound(sensor_raw: str) -> str:
    """
    Sensor raw comes as a hex string from tcp_session.cpp (sensor_raw).
    In pi_comm.cpp, '1' means obstacle, '0' means clear.
    We approximate ultrasound distance:
      - obstacle ('1') -> 0 cm
      - clear   ('0') -> ultra_max
    """
    parts = sensor_raw.strip().split()
    if not parts:
        return "--"
    last_hex = parts[-1]
    try:
        b = int(last_hex, 16)
    except ValueError:
        return "--"

    # ASCII '1' / '0'
    if b == ord('1'):
        return "0"
    elif b == ord('0'):
        try:
            return str(int(ultra_max.get()))
        except ValueError:
            return "300"
    else:
        # Unknown state, just show raw value
        return f"? ({last_hex})"

def apply_telemetry(obj):
    global odo_value

    seq = obj.get("seq")
    if seq is not None:
        seq_v.set(str(seq))

    batt = obj.get("batt_v")
    if isinstance(batt, (int, float)):
        volt_v.set(f"{batt:.2f}")

    speed = obj.get("speed")
    if isinstance(speed, (int, float)):
        # speed is m/s in C++ -> km/h
        kmh = speed * 3.6
        speed_kmh_v.set(f"{kmh:.1f}")
        # simple odometer estimate assuming ~20 Hz telemetry
        dt = 0.05  # 50 ms
        odo_value += speed * dt
        odometer_v.set(f"{odo_value:.1f}")

    raw = obj.get("sensor_raw")
    if isinstance(raw, str):
        ultrasound_v.set(interpret_ultrasound(raw))

def rx_telemetry():
    buf = b""
    while True:
        try:
            data = s.recv(1024)
            if not data:
                append_log("Connection closed by server")
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                txt = line.decode("utf-8", "ignore").strip()
                if not txt:
                    continue
                try:
                    obj = json.loads(txt)
                except json.JSONDecodeError:
                    append_log(f"Bad telemetry: {txt}")
                    continue
                # Schedule UI update in main thread
                root.after(0, apply_telemetry, obj)
        except OSError as e:
            append_log(f"Telemetry error: {e}")
            break

# === [NYTT] Video-mottagning ===
def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf

def update_cam_image(pil_img):
    global _cam_img_ref
    pil_img = pil_img.resize((CAM_W, CAM_H))
    tk_img = ImageTk.PhotoImage(pil_img)
    _cam_img_ref = tk_img
    cam_label.config(image=tk_img, text="")

def rx_video():
    if not video_connected or vsock is None:
        return
    try:
        while True:
            hdr = recv_exact(vsock, 4)
            if not hdr:
                append_log("Video: ström avslutad")
                break
            (length,) = struct.unpack("!I", hdr)
            data = recv_exact(vsock, length)
            if not data:
                append_log("Video: ström avslutad (payload)")
                break
            try:
                img = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                continue
            root.after(0, update_cam_image, img)
    except OSError as e:
        append_log(f"Video error: {e}")
    finally:
        try:
            if vsock:
                vsock.close()
        except Exception:
            pass

# Start telemetry + video threads
threading.Thread(target=rx_telemetry, daemon=True).start()
threading.Thread(target=rx_video, daemon=True).start()

# === Clean shutdown ===
def on_close():
    try:
        # använder fortfarande rörelseprotokollet för "quit"
        send("quit")
        s.close()
    except Exception:
        pass
    try:
        if vsock:
            vsock.close()
    except Exception:
        pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

# === Main loop ===
root.mainloop()