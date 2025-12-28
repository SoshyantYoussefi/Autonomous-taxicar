import socket
import threading
import sys
import json
import time
import tkinter as tk
from tkinter import ttk

# === För video-dekod & protokoll ===
import struct
import io
try:
    from PIL import Image, ImageTk
except ImportError:
    raise SystemExit("Installera Pillow först: pip install pillow")


# ----------- MOVE DATA -------------- #

with open("move_data.json", "r", encoding="utf-8") as f:
    MOVE_COMMAND_MAP = json.load(f)["move_data"]
# t.ex. {"forward_down": 0x01, "forward_up": 0x02, ...}

# === OPCODES (matchar din C-enum) ===
MOVE_COMMAND = 0x01
VAXLING = 0x02

OPCODE_HALL = 0x03
OPCODE_ULTRASONIC = 0x04

OFFSET_ANGLE = 0x10

OPCODE_SET_PID_P = 0x11
OPCODE_SET_PID_I = 0x12
OPCODE_SET_PID_D = 0x20

OPCODE_CALIB_HALL = 0x30

# Algorithm start/stop (välj värden som matchar Pi-sidan)
OPCODE_ALGO_START = 0x40
OPCODE_ALGO_STOP = 0x41

OPCODE_SPEED_MODE = 0x50


# Samlade namn för logging / debug
OPCODE_NAMES = {
    MOVE_COMMAND: "MOVE_COMMAND",
    VAXLING: "VAXLING",
    OPCODE_HALL: "OPCODE_HALL",
    OPCODE_ULTRASONIC: "OPCODE_ULTRASONIC",
    OFFSET_ANGLE: "OFFSET_ANGLE",
    OPCODE_SET_PID_P: "OPCODE_SET_PID_P",
    OPCODE_SET_PID_I: "OPCODE_SET_PID_I",
    OPCODE_SET_PID_D: "OPCODE_SET_PID_D",
    OPCODE_CALIB_HALL: "OPCODE_CALIB_HALL",
    OPCODE_ALGO_START: "OPCODE_ALGO_START",
    OPCODE_ALGO_STOP: "OPCODE_ALGO_STOP",
    OPCODE_SPEED_MODE: "OPCODE_SPEED_MODE",
}

# === Host → Pi Packet Formats ===
#
# MOVE_COMMAND (0x01)
# [opcode][data]
# data: uint8 från MOVE_COMMAND_MAP (forward_down, left_up, etc.)
#
# VAXLING (0x02)
# [opcode][mode]
# mode: uint8
# 0x00 = Manual
# 0x01 = Autonomous
#
# OPCODE_HALL (0x03)
# [opcode]
# (ingen payload just nu)
#
# OPCODE_ULTRASONIC (0x04)
# [opcode][max_distance_cm]
# max_distance_cm: uint8 (0–255)
#
# OFFSET_ANGLE (0x10)
# [opcode][vinkel ...] (om/ när det används)
#
# OPCODE_SET_PID_P (0x11)
# [opcode][P]
# P: uint8, 0–250  (GUI sends 0.00–5.00 scaled by ×50)
#
# OPCODE_SET_PID_I (0x12)
# [opcode][I]
# I: uint8, 0–250  (GUI sends 0.00–5.00 scaled by ×50)
#
# OPCODE_SET_PID_D (0x20)
# [opcode][D]
# D: uint8, 0–250  (GUI sends 0.00–5.00 scaled by ×50)
#
# OPCODE_CALIB_HALL (0x30)
# [opcode]
# (ingen payload – triggar kalibrering)
#
# OPCODE_ALGO_START (0x40)
# [opcode][start][middle][end]
# start, middle, end: uint8
# 0xFF = "no node" (t.ex. '-')
# a1..d2 -> 0x00..0x07 in the low nibble:
# a1=0000, a2=0001, b1=0010, b2=0011, c1=0100, c2=0101, d1=0110, d2=0111
#
# OPCODE_ALGO_STOP (0x41)
# [opcode]


# används för rörelsekommandon: [MOVE_COMMAND][DATA_BYTE]
move_opcode = MOVE_COMMAND


# === Network / Connection ===

PI_IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.42"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 5000

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
s.connect((PI_IP, PORT))

# Video-port + socket (andra TCP-anslutningen)
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
bg_dark = "#1e1e1e"
card_bg = "#2b2b2b"
button_bg = "#3a3a3a"
button_hover = "#5a5a5a"
button_active = "#777777"
text_light = "#f5f5f5"
accent = "#aaaaaa"

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
speed_kmh_v = tk.StringVar(value="--")
ultrasound_v = tk.StringVar(value="--")
odometer_v = tk.StringVar(value="--")
logs_v = tk.StringVar(value="")
ultra_max = tk.StringVar(value="--")

# PID vars
pid_kp = tk.StringVar(value="1.0")
pid_ki = tk.StringVar(value="0.0")
pid_kd = tk.StringVar(value="0.0")

# Algorithm node vars
algo_start_node = tk.StringVar(value="")
algo_middle_node = tk.StringVar(value="")
algo_end_node = tk.StringVar(value="")

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


tele_label(2, "Speed (m/s):", speed_kmh_v)

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


sensor_label(0, "Ultrasound:", ultrasound_v)
sensor_label(1, "Körd sträcka (m):", odometer_v)

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


# --- GENERELL BYTES-SENDFUNKTION ---

def send_speed_mode(mode):
    modes = {"Slow": 0x37, "Medium": 0x3D, "Fast": 0x42}
    value = modes.get(mode, 0x00)
    send_opcode(OPCODE_SPEED_MODE, bytes([value]))
    append_log(f"Set speed mode to {mode} (0x{value:02X})")


def send_bytes(pkt: bytes, description: str = ""):
    """
    Generell funktion för att skicka godtycklig byte-sekvens över s.
    ALLA andra 'send' helpers går via denna.
    """
    try:
        s.sendall(pkt)
        if description:
            append_log(f"{description} | raw={pkt.hex()}")
        else:
            append_log(f"Sent raw={pkt.hex()}")
        print(f"Sent: {description} | raw={pkt.hex()}")
    except OSError as e:
        append_log(f"Send error: {e}")
        print(f"Send error: {e}")


# --- Högre nivå: movement & opcode ---


def send_move(cmd: str):
    """
    Movement packet:
    [MOVE_COMMAND][DATA_BYTE]

    DATA_BYTE tas från move_data.json via MOVE_COMMAND_MAP dict.
    """
    if cmd not in MOVE_COMMAND_MAP:
        append_log(f"Unknown move command: {cmd}")
        return

    data_byte = MOVE_COMMAND_MAP[cmd] & 0xFF
    pkt = bytes([move_opcode & 0xFF, data_byte])
    desc = f"MOVE {cmd} (opcode=0x{move_opcode:02X}, data=0x{data_byte:02X})"
    send_bytes(pkt, desc)


# Behåll samma namn som tidigare för kompatibilitet
def send(cmd: str):
    send_move(cmd)


def send_opcode(opcode: int, payload: bytes = b""):
    """
    Generic opcode packet:
    [OPCODE][PAYLOAD...]

    OPCODE är 1 byte (matchar din C-enum).
    """
    opcode_byte = opcode & 0xFF
    pkt = bytes([opcode_byte]) + (payload or b"")
    name = OPCODE_NAMES.get(opcode_byte, f"0x{opcode_byte:02X}")
    if payload:
        desc = f"OPCODE {name}, payload={payload.hex()}"
    else:
        desc = f"OPCODE {name}, no payload"
    send_bytes(pkt, desc)


# --- PID helpers ---
SCALE_PID = 50.0  # 0.00–5.00 -> 0–250   (0.02 resolution)


def _encode_pid_byte(value: float) -> int:
    """
    Clamp 0.0–5.0, scale with ×50, return uint8 (0–250).
    """
    try:
        v = float(value)
    except ValueError:
        raise ValueError(f"Bad PID value: {value}")

    # clamp to [0.0, 5.0]
    if v < 0.0:
        v = 0.0
    if v > 5.0:
        v = 5.0

    encoded = int(round(v * SCALE_PID))  # 0.00–5.00 => 0–250
    if encoded < 0:
        encoded = 0
    if encoded > 255:
        encoded = 255
    return encoded


def send_pid_p(value: float):
    """
    [OPCODE_SET_PID_P][P as uint8, scaled 0.00–5.00 ×50]
    """
    try:
        b = _encode_pid_byte(value)
    except ValueError as e:
        append_log(str(e))
        return
    send_opcode(OPCODE_SET_PID_P, bytes([b]))


def send_pid_i(value: float):
    """
    [OPCODE_SET_PID_I][I as uint8, scaled 0.00–5.00 ×50]
    """
    try:
        b = _encode_pid_byte(value)
    except ValueError as e:
        append_log(str(e))
        return
    send_opcode(OPCODE_SET_PID_I, bytes([b]))


def send_pid_d(value: float):
    """
    [OPCODE_SET_PID_D][D as uint8, scaled 0.00–5.00 ×50]
    """
    try:
        b = _encode_pid_byte(value)
    except ValueError as e:
        append_log(str(e))
        return
    send_opcode(OPCODE_SET_PID_D, bytes([b]))

# --- Algorithm helpers ---


NODE_CODE_MAP = {
    "a1": 0x00,
    "a2": 0x01,
    "b1": 0x02,
    "b2": 0x03,
    "c1": 0x04,
    "c2": 0x05,
    "d1": 0x06,
    "d2": 0x07,
}

def send_algo_start(start: str, middle: str, end: str):
    """
    Skicka tre noder som bytes:

    [OPCODE_ALGO_START][start][middle][end]

    Tomma fält -> 0x00.
    I övrigt används första tecknet i strängen, t.ex. 'A' -> 0x41.
    """

    def encode_node(s: str) -> int:
        s = (s or "").strip()
        if not s or s == "-":
            return 0
        return ord(s[0]) & 0xFF

    payload = bytes(
        [
            encode_node(start),
            encode_node(middle),
            encode_node(end),
        ]
    )
    send_opcode(OPCODE_ALGO_START, payload)


def send_algo_stop(reason: int | None = None):
    """
    [OPCODE_ALGO_STOP][optional reason]
    """
    if reason is None:
        payload = b""
    else:
        payload = bytes([reason & 0xFF])

    send_opcode(OPCODE_ALGO_STOP, payload)


# === Controls Card ===
controls_card = create_card(main_frame, "Controls")

# === Mode Toggle ===
mode_state = tk.StringVar(value="Manual")


def set_mode(mode):
    mode_state.set(mode)
    append_log(f"Mode set to {mode}")

    # Skicka mode till Pi via VAXLING:
    # 0x00 = Manual, 0x01 = Autonomous
    value = 0x00 if mode == "Manual" else 0x01
    send_opcode(VAXLING, bytes([value]))


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


make_toggle("Manual", "Manual", 0)
make_toggle("Autonomous", "Autonomous", 2)

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
            send_move(cmd_down)

    def release():
        b.config(bg=button_bg)
        if cmd_up:
            send_move(cmd_up)

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
    b.bind("<Button-1>", lambda e: press())
    b.bind("<ButtonRelease-1>", lambda e: release())

    if key:
        active_buttons[key] = (b, press, release)


# Map GUI buttons -> JSON movement command names
make_button("↑ Forward", "forward_down", "forward_up", 1, 1, "Up")
make_button("← Left", "left_down", "left_up", 2, 0, "Left")
make_button("Stop", "stop_down", "stop_up", 2, 1, "space")
make_button("Right →", "right_down", "right_up", 2, 2, "Right")
make_button("↓ Backward", "backward_down", "backward_up", 3, 1, "Down")

for i in range(3):
    controls_card.columnconfigure(i, weight=1)

# === Autonomous Algorithm Card ===
algo_card = create_card(main_frame, "Autonomous Algorithm")
algo_wrapper = algo_card.master

tk.Label(
    algo_card,
    text="Enter nodes (comma-separated, e.g. A1, C2):",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).grid(row=0, column=0, sticky="w", padx=10, pady=4)

algo_nodes_str = tk.StringVar(value="")   # <-- här lagras texten
algo_nodes_entry = tk.Entry(
    algo_card,
    textvariable=algo_nodes_str,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=25,
    justify="center",
    font=("Consolas", 10),
)
algo_nodes_entry.grid(row=0, column=1, sticky="w", padx=10, pady=4)

NODE_HEX_MAP = {
    "A1": 0xA1,
    "A2": 0xA2,
    "B1": 0xB1,
    "B2": 0xB2,
    "C1": 0xC1,
    "C2": 0xC2,
    "D1": 0xD1,
    "D2": 0xD2,
}

def send_algo_start_array():
    raw = algo_nodes_str.get().strip()
    if not raw:
        append_log("Algorithm: no nodes entered")
        return

    nodes = [n.strip().upper() for n in raw.split(",") if n.strip()]

    payload_bytes = []
    for node in nodes:
        if len(node) != 2 or not node[0].isalpha() or not node[1].isdigit():
            append_log(f"Invalid node format: {node}")
            return
        # Lägg in varje tecken som EGEN BYTE
        payload_bytes.append(ord(node[0]))  # 'A' -> 0x41
        payload_bytes.append(ord(node[1]))  # '1' -> 0x31

    length_byte = len(payload_bytes)  # faktiska antal bytes

    pkt = bytes([OPCODE_ALGO_START, length_byte] + payload_bytes)

    send_bytes(pkt, f"ALGO_START send {nodes}")
    append_log(f"Sent ALGO_START with {len(nodes)} nodes: {nodes}")

def algo_stop():
    send_algo_stop(0x00)


# Start / Stop buttons
algo_start_btn = tk.Label(
    algo_card,
    text="Start",
    bg=button_bg,
    fg=text_light,
    font=("Consolas", 10),
    width=10,
    height=1,
    relief="flat",
    cursor="hand2",
)
algo_start_btn.grid(row=3, column=0, padx=10, pady=(6, 6), sticky="w")

algo_stop_btn = tk.Label(
    algo_card,
    text="Stop",
    bg=button_bg,
    fg=text_light,
    font=("Consolas", 10),
    width=10,
    height=1,
    relief="flat",
    cursor="hand2",
)
algo_stop_btn.grid(row=3, column=1, padx=10, pady=(6, 6), sticky="w")

# Hover + click bindings for algorithm buttons
algo_start_btn.bind("<Enter>", lambda e: algo_start_btn.config(bg=button_hover))
algo_start_btn.bind("<Leave>", lambda e: algo_start_btn.config(bg=button_bg))
algo_start_btn.bind("<Button-1>", lambda e: send_algo_start_array())

algo_stop_btn.bind("<Enter>", lambda e: algo_stop_btn.config(bg=button_hover))
algo_stop_btn.bind("<Leave>", lambda e: algo_stop_btn.config(bg=button_bg))
algo_stop_btn.bind("<Button-1>", lambda e: algo_stop())

# === Side Panel: Ultrasound Calibration ===
calib_card = create_card(side_frame, "Ultrasound Calibration")

tk.Label(
    calib_card,
    text="Max Distance:",
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
        if not 0 <= num <= 255:
            raise ValueError

        append_log(f"Applied ultrasound max distance: {num}")
        # skicka 1 byte (0–255 cm) till Pi
        send_opcode(OPCODE_ULTRASONIC, num.to_bytes(1, "big"))

    except ValueError:
        append_log("Invalid calibration value! (måste vara 0–255)")


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

# === Side Panel: PID Calibration ===
pid_card = create_card(side_frame, "PID Calibration")
pid_wrapper = pid_card.master  # wrapper that packas/unpackas

# Use a horizontal grid layout:  Kp  Ki  Kd  all in one row

# Kp
tk.Label(
    pid_card,
    text="Kp:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).grid(row=0, column=0, pady=(0, 2), padx=(10, 4), sticky="w")

kp_entry = tk.Entry(
    pid_card,
    textvariable=pid_kp,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=6,
    justify="center",
    font=("Consolas", 10),
)
kp_entry.grid(row=0, column=1, pady=(0, 2), padx=(0, 10), sticky="w")

# Ki
tk.Label(
    pid_card,
    text="Ki:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).grid(row=0, column=2, pady=(0, 2), padx=(0, 4), sticky="w")

ki_entry = tk.Entry(
    pid_card,
    textvariable=pid_ki,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=6,
    justify="center",
    font=("Consolas", 10),
)
ki_entry.grid(row=0, column=3, pady=(0, 2), padx=(0, 10), sticky="w")

# Kd
tk.Label(
    pid_card,
    text="Kd:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).grid(row=0, column=4, pady=(0, 2), padx=(0, 4), sticky="w")

kd_entry = tk.Entry(
    pid_card,
    textvariable=pid_kd,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=6,
    justify="center",
    font=("Consolas", 10),
)
kd_entry.grid(row=0, column=5, pady=(0, 2), padx=(0, 10), sticky="w")


def apply_pid():
    try:
        kp = float(pid_kp.get())
        ki = float(pid_ki.get())
        kd = float(pid_kd.get())
    except ValueError:
        append_log("Invalid PID value! (use numbers)")
        return

    send_pid_p(kp)
    send_pid_i(ki)
    send_pid_d(kd)
    append_log(f"Applied PID: Kp={kp:.3f}, Ki={ki:.3f}, Kd={kd:.3f}")


pid_apply_btn = tk.Label(
    pid_card,
    text="Apply PID",
    bg=button_bg,
    fg=text_light,
    font=("Consolas", 10),
    width=10,
    height=1,
    relief="flat",
    cursor="hand2",
)
pid_apply_btn.grid(row=1, column=0, columnspan=6, padx=10, pady=4, sticky="w")

pid_apply_btn.bind("<Enter>", lambda e: pid_apply_btn.config(bg=button_hover))
pid_apply_btn.bind("<Leave>", lambda e: pid_apply_btn.config(bg=button_bg))
pid_apply_btn.bind("<Button-1>", lambda e: apply_pid())

# === Side Panel: Speed Mode Selection ===
speed_card = create_card(side_frame, "Speed Mode")

speed_mode_var = tk.StringVar(value="Medium")  # default

def make_speed_button(text, mode, col):
    b = tk.Label(
        speed_card,
        text=text,
        bg=button_bg,
        fg=text_light,
        font=("Consolas", 10),
        width=10,
        height=1,
        relief="flat",
        cursor="hand2",
    )
    b.grid(row=0, column=col, padx=6, pady=5, sticky="w")

    def on_click():
        speed_mode_var.set(mode)
        send_speed_mode(mode)
        update_buttons()

    def update_buttons():
        for widget in speed_card.winfo_children():
            if isinstance(widget, tk.Label):
                if widget.cget("text") == speed_mode_var.get():
                    widget.config(bg=button_active)
                else:
                    widget.config(bg=button_bg)

    b.bind("<Button-1>", lambda e: on_click())
    update_buttons()

# Put modes next to each other horizontally
make_speed_button("Slow", "Slow", 0)
make_speed_button("Medium", "Medium", 1)
make_speed_button("Fast", "Fast", 2)

# === Camera Card ===
camera_card = create_card(side_frame, "Camera")

# Bildyta för kameraflöde
cam_label = tk.Label(
    camera_card,
    bg=card_bg,
    fg=accent,
    #width=100,
    #height=100,
    anchor="center",
    justify="center",
)
cam_label.pack(padx=10, pady=10)
_cam_img_ref = None  # behåll referens så bilden inte garbage-collectas
CAM_W, CAM_H = 400, 300  # visningsstorlek

if not video_connected:
    cam_label.config(text="[No camera feed]", fg=accent)


# === Show/hide autonomous stuff based on mode ===
def on_mode_change(*_):
    if mode_state.get() == "Autonomous":
        # show autonomous algorithm and PID
        algo_wrapper.pack(fill="x", padx=15, pady=(12, 6))
        pid_wrapper.pack(fill="x", padx=15, pady=(12, 6))
    else:
        # hide them in Manual mode
        algo_wrapper.pack_forget()
        pid_wrapper.pack_forget()


mode_state.trace_add("write", lambda *args: on_mode_change())
# Apply initial state (Manual)
on_mode_change()

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
    I pi_comm.cpp, '1' betyder hinder, '0' betyder fritt.
    Vi approximerar ultrasound-avstånd:
    - hinder ('1') -> 0 cm
    - fritt ('0') -> ultra_max
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
    if b == ord("1"):
        return "0"
    elif b == ord("0"):
        try:
            return str(int(ultra_max.get()))
        except ValueError:
            return "300"
    else:
        # Unknown state, just show raw value
        return f"? ({last_hex})"


def apply_telemetry(obj):
    # Speed is in m/s from the backend
    speed = obj.get("speed")
    if isinstance(speed, (int, float)):
        speed_kmh_v.set(f"{speed:.2f}")

    # Distance is in meters from the backend
    distance = obj.get("distance")
    if isinstance(distance, (int, float)):
        odometer_v.set(f"{distance:.2f}")

    ultrasound = obj.get("ultrasound")
    if ultrasound in [0, 1]:
        ultrasound_v.set(str(ultrasound))
    else:
        ultrasound_v.set("--")


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


# === Video-mottagning ===
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


# === Clicking outside: DON'T steal focus from Entry widgets ===
def unfocus(event):
    # Only steal focus if it's not an Entry (så du kan skriva i alla inputs)
    if not isinstance(event.widget, tk.Entry):
        root.focus()


root.bind_all("<Button-1>", unfocus, add="+")


# === Clean shutdown ===
def on_close():
    try:
        # använder fortfarande rörelseprotokollet för "quit"
        send_move("quit")
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
