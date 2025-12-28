# pip install tkinterweb==0.0.4 (valfritt)  # Tkinter ingår i vanliga Python på Windows
# Kör: python win_gui.py 192.168.1.42 5000

import socket, threading, sys, tkinter as tk 
from tkinter import ttk  #tkinter python gui bibliotek, ttk = themed tkinter
import json  

PI_IP = sys.argv[1] if len(sys.argv)>1 else "192.168.1.42" #Hämta ip  från kommandoraden.
PORT  = int(sys.argv[2]) if len(sys.argv)>2 else 5000   #Hämta port från kommandoraden

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  #skapa tcp anslutning. sockstream = tcp (sock_dgram = udp)
#af inet = address family: inteernet dvs ipv4  internet protokollet.
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1) #nodelay tar bort nagles algoritm (inte vänta på småskit att skickas samtidigt.)
s.connect((PI_IP, PORT)) #koppla till raspberryns ip och port

root = tk.Tk() #skapa fönstret
root.title("Max Verstappen controller (TCP)")

#Gui info 
status = tk.StringVar(value="Connected to %s:%d" % (PI_IP, PORT)) 
tele_v = tk.StringVar(value="V=--.-V  v=--.-  seq=--") #telemetridata
ttk.Label(root, textvariable=status).pack(anchor="w", padx=10, pady=6) # font och storlekt mm
ttk.Label(root, textvariable=tele_v, font=("Consolas",12)).pack(anchor="w", padx=10) #-||-
sensor_v = tk.StringVar(value="sensor: --")  
ttk.Label(root, textvariable=sensor_v, font=("Consolas",10)).pack(anchor="w", padx=10)  


frm = ttk.Frame(root); frm.pack(padx=10, pady=10) #gui ruta, sstorlekt 10,10
def send(cmd: str): #hjälpfunktion varje gång vi skickar till pi:n. 
    try: s.sendall((cmd+"\n").encode("utf-8")) #\n ger radbrytning .encode utf 8 omvandlar texten till bytes. sendall skickar hela meddelandent över tcp socketen s.
    except OSError: status.set("Disconnected") #Vid error sätt status till disconnected.

#fixar gui knapparna i frame, kopplas till kommandon mha command= . 
# ttk.Button(frm, text="↑ Framåt", width=14, command=on_up).grid(row=0, column=1, padx=5, pady=5)
# ttk.Button(frm, text="← Vänster", width=14, command=on_left).grid(row=1, column=0, padx=5, pady=5)
# ttk.Button(frm, text="Stopp", width=14, command=on_space).grid(row=1, column=1, padx=5, pady=5)
# ttk.Button(frm, text="Höger →", width=14, command=on_right).grid(row=1, column=2, padx=5, pady=5)
# ttk.Button(frm, text="↓ Bakåt", width=14, command=on_down).grid(row=2, column=1, padx=5, pady=5)

pressed_keys = set()  # globalt minne av aktiva tangenter

def on_key_press(event):
    key = event.keysym  # t.ex. "Up", "Left", "space"

    if key not in pressed_keys:  # första gången knappen trycks
        pressed_keys.add(key)

        if key == "Up":           send("fram_down")
        elif key == "Down":       send("bakåt_down")
        elif key == "Left":       send("vänster_down")
        elif key == "Right":      send("höger_down")
        elif key == "space":      send("stop_down")

def on_key_release(event):
    key = event.keysym

    if key in pressed_keys:
        pressed_keys.remove(key)

        if key == "Up":           send("fram_up")
        elif key == "Down":       send("bakåt_up")
        elif key == "Left":       send("vänster_up")
        elif key == "Right":      send("höger_up")
        elif key == "space":      send("stop_up")

# Bind:
root.bind_all("<KeyPress>", on_key_press)
root.bind_all("<KeyRelease>", on_key_release)


#hämtar data och visar den i gui 
def rx_telemetry():
    buf = b""
    while True:
        try:
            data = s.recv(1024) #läser in max 1024 bytes från tcp socket s.
            if not data: break #om ingen data bryt loopen och kalla oserror.
            buf += data
            while b"\n" in buf: #när radslut har kommit, dvs ett helt meddelande finns
                line, buf = buf.split(b"\n", 1) #splitta efter radbrytning
                txt = line.decode("utf-8", "ignore") #omvandla tillbaka från bytes till sträng 
                # Minimal parsing utan json: plocka ut siffror grovt
                # (Byt gärna till json.loads för robusthet.)
                # Ex: {"seq":12,"batt_v":7.62,"speed":3.20,"t":123.456}
            try:
                obj = json.loads(txt)  # Pi sends one JSON object per line
                seq = int(obj.get("seq", -1))
                v   = float(obj.get("batt_v", 0.0))
                sp  = float(obj.get("speed", 0.0))
                tele_v.set(f"V={v:.2f}V  v={sp:.2f}  seq={seq}")

                # Show sensor_raw (hex string) if present
                raw = obj.get("sensor_raw", "")
                if isinstance(raw, str) and raw:
                    grouped = " ".join(raw[i:i+2] for i in range(0, len(raw), 2))  # "AABB" -> "AA BB"
                    sensor_v.set(f"sensor: {grouped}")
                else:
                    sensor_v.set("sensor: --")
            except Exception:
                tele_v.set(txt[:60])
                sensor_v.set("sensor: --")
        except OSError:
            break

threading.Thread(target=rx_telemetry, daemon=True).start() #bakgrundstråd för telemetrin daemon anger att det är en bakgrundstråd. 
#start startar bakgrundstråden direkt.

def on_close(): #logik för att stänga GUI
    try: s.sendall(b"quit\n"); s.close()
    except: pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop() #startar mainloopen
