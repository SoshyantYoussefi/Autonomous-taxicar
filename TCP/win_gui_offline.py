# Max Verstappen Controller (Offline Test)

import tkinter as tk
from tkinter import ttk
import random, threading, time

# === Root Window Setup ===
root = tk.Tk()
root.title("Max Verstappen Controller (Offline Test)")

# Force fullscreen:
root.attributes("-fullscreen", True)

# (Optional: let Esc exit fullscreen)
root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))

root.configure(bg="#1e1e1e")

# === Color Scheme ===
bg_dark = "#1e1e1e"
card_bg = "#2b2b2b"
button_bg = "#3a3a3a"
button_hover = "#5a5a5a"
button_active = "#777777"
text_light = "#f5f5f5"
accent = "#aaaaaa"

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
volt_v       = tk.StringVar(value="--.--")
seq_v        = tk.StringVar(value="--")
speed_kmh_v  = tk.StringVar(value="--")
ultrasound_v = tk.StringVar(value="--")
odometer_v   = tk.StringVar(value="--")
logs_v       = tk.StringVar(value="")
ultra_max    = tk.StringVar(value="300")

# PID vars
pid_kp = tk.StringVar(value="1.0")
pid_ki = tk.StringVar(value="0.0")
pid_kd = tk.StringVar(value="0.0")

# Algorithm node vars
algo_start_node  = tk.StringVar(value="")
algo_middle_node = tk.StringVar(value="")
algo_end_node    = tk.StringVar(value="")

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

tele_label(0, "Battery (V):",  volt_v)
tele_label(1, "seq:",          seq_v)
tele_label(2, "Speed (km/h):", speed_kmh_v)

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

def send(cmd: str):
    print(f"Sent command: {cmd}")
    append_log(cmd)

# === Controls Card ===
controls_card = create_card(main_frame, "Controls")

# === Mode Toggle ===
mode_state = tk.StringVar(value="Manual")

def set_mode(mode):
    mode_state.set(mode)
    append_log(f"Mode set to {mode}")

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

make_toggle("Manual",     "Manual",     0)
make_toggle("Autonomous", "Autonomous", 2)

# === Movement Buttons ===
active_buttons = {}

def make_button(text, command, r, c, key=None):
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
        command()

    def release():
        b.config(bg=button_bg)

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
    b.bind("<Button-1>",        lambda e: press())
    b.bind("<ButtonRelease-1>", lambda e: release())

    if key:
        active_buttons[key] = (b, press, release)

make_button("↑ Forward",   lambda: send("forward_down"),   1, 1, "Up")
make_button("← Left",      lambda: send("left_down"),      2, 0, "Left")
make_button("Stop",        lambda: send("stop_down"),      2, 1, "space")
make_button("Right →",     lambda: send("right_down"),     2, 2, "Right")
make_button("↓ Backward",  lambda: send("backward_down"),  3, 1, "Down")

for i in range(3):
    controls_card.columnconfigure(i, weight=1)

# === Autonomous Algorithm Card (under Controls) ===
algo_card = create_card(main_frame, "Autonomous Algorithm")
algo_wrapper = algo_card.master  # wrapper that actually gets packed

# Grid config inside algorithm card
for i in range(2):
    algo_card.columnconfigure(i, weight=1)

# Start node
tk.Label(
    algo_card,
    text="Start Node:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).grid(row=0, column=0, sticky="w", padx=10, pady=(4, 2))

algo_start_entry = tk.Entry(
    algo_card,
    textvariable=algo_start_node,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=12,
    justify="center",
    font=("Consolas", 10),
)
algo_start_entry.grid(row=0, column=1, sticky="w", padx=10, pady=(4, 2))

# Middle node
tk.Label(
    algo_card,
    text="Middle Node:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).grid(row=1, column=0, sticky="w", padx=10, pady=2)

algo_middle_entry = tk.Entry(
    algo_card,
    textvariable=algo_middle_node,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=12,
    justify="center",
    font=("Consolas", 10),
)
algo_middle_entry.grid(row=1, column=1, sticky="w", padx=10, pady=2)

# End node
tk.Label(
    algo_card,
    text="End Node:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).grid(row=2, column=0, sticky="w", padx=10, pady=2)

algo_end_entry = tk.Entry(
    algo_card,
    textvariable=algo_end_node,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=12,
    justify="center",
    font=("Consolas", 10),
)
algo_end_entry.grid(row=2, column=1, sticky="w", padx=10, pady=2)

def algo_start():
    s = algo_start_node.get().strip()
    m = algo_middle_node.get().strip()
    e = algo_end_node.get().strip()
    if not s or not e:
        append_log("Algorithm: start and end should not be empty")
    cmd = f"algo_start {s or '-'} {m or '-'} {e or '-'}"
    send(cmd)

def algo_stop():
    send("algo_stop")

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
algo_start_btn.bind("<Button-1>", lambda e: algo_start())

algo_stop_btn.bind("<Enter>", lambda e: algo_stop_btn.config(bg=button_hover))
algo_stop_btn.bind("<Leave>", lambda e: algo_stop_btn.config(bg=button_bg))
algo_stop_btn.bind("<Button-1>", lambda e: algo_stop())

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

# Enter key applies + unfocuses for ultrasound entry
def on_apply_key(event=None):
    apply_calibration()
    root.focus()

entry.bind("<Return>", on_apply_key)

# === Side Panel: PID Calibration ===
pid_card = create_card(side_frame, "PID Calibration")
pid_wrapper = pid_card.master  # wrapper that gets packed/unpacked

# Kp
tk.Label(
    pid_card,
    text="Kp:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).pack(anchor="w", pady=(0, 2), padx=10)

kp_entry = tk.Entry(
    pid_card,
    textvariable=pid_kp,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=10,
    justify="center",
    font=("Consolas", 10),
)
kp_entry.pack(anchor="w", padx=10, pady=(0, 4))

# Ki
tk.Label(
    pid_card,
    text="Ki:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).pack(anchor="w", pady=(0, 2), padx=10)

ki_entry = tk.Entry(
    pid_card,
    textvariable=pid_ki,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=10,
    justify="center",
    font=("Consolas", 10),
)
ki_entry.pack(anchor="w", padx=10, pady=(0, 4))

# Kd
tk.Label(
    pid_card,
    text="Kd:",
    bg=card_bg,
    fg=text_light,
    font=("Consolas", 10),
).pack(anchor="w", pady=(0, 2), padx=10)

kd_entry = tk.Entry(
    pid_card,
    textvariable=pid_kd,
    bg=button_bg,
    fg=text_light,
    insertbackground=text_light,
    relief="flat",
    width=10,
    justify="center",
    font=("Consolas", 10),
)
kd_entry.pack(anchor="w", padx=10, pady=(0, 6))

def apply_pid():
    try:
        kp = float(pid_kp.get())
        ki = float(pid_ki.get())
        kd = float(pid_kd.get())
    except ValueError:
        append_log("Invalid PID value! (use numbers)")
        return

    cmd = f"pid {kp:.3f} {ki:.3f} {kd:.3f}"
    send(cmd)
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
pid_apply_btn.pack(anchor="w", padx=10, pady=4)

pid_apply_btn.bind("<Enter>", lambda e: pid_apply_btn.config(bg=button_hover))
pid_apply_btn.bind("<Leave>", lambda e: pid_apply_btn.config(bg=button_bg))
pid_apply_btn.bind("<Button-1>", lambda e: apply_pid())

# === Camera Card ===
camera_card = create_card(side_frame, "Camera")
tk.Label(
    camera_card,
    text="[Camera feed not available in offline mode]",
    bg=card_bg,
    fg=accent,
    font=("Consolas", 10),
    height=10,
    width=35,
    anchor="center",
    justify="center",
).pack(padx=10, pady=10)

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
        active_buttons[key][0].config(bg=button_active)
        active_buttons[key][1]()  # press action

def on_key_release(event):
    key = event.keysym
    if key in pressed_keys and key in active_buttons:
        pressed_keys.remove(key)
        active_buttons[key][0].config(bg=button_bg)
        active_buttons[key][2]()  # release action

root.bind_all("<KeyPress>", on_key_press)
root.bind_all("<KeyRelease>", on_key_release)

# === Clicking outside: DON'T steal focus from Entry widgets ===
def unfocus(event):
    # Only steal focus if it's not an Entry (so you can type in all inputs)
    if not isinstance(event.widget, tk.Entry):
        root.focus()

root.bind_all("<Button-1>", unfocus, add="+")

# === Fake Telemetry Thread ===
def fake_telemetry():
    seq = 0
    while True:
        seq += 1
        v = 7.0 + random.random() * 0.6
        sp = random.random() * 5
        kmh = sp * 3.6
        ultra = random.randint(
            5,
            int(ultra_max.get()) if ultra_max.get().isdigit() else 300,
        )
        odo = seq * 0.25

        volt_v.set(f"{v:.2f}")
        seq_v.set(str(seq))
        speed_kmh_v.set(f"{kmh:.1f}")
        ultrasound_v.set(f"{ultra}")
        odometer_v.set(f"{odo:.1f}")
        time.sleep(1)

threading.Thread(target=fake_telemetry, daemon=True).start()

# === Final Setup ===
root.protocol("WM_DELETE_WINDOW", root.destroy)
root.mainloop()