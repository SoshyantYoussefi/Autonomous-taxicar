import socket
import os

SOCK = "/tmp/drive_cmd.sock"

# Ta bort gammal fil om den finns
if os.path.exists(SOCK):
    os.remove(SOCK)

s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
s.bind(SOCK)

print("Fake kamera lyssnar på /tmp/drive_cmd.sock...")

while True:
    data, addr = s.recvfrom(1)
    cmd = data[0]
    print(f"Fake kamera fick kommando: {cmd}")

    # Skicka DONE tillbaka
    s.sendto(b"D", addr)
    print("Fake kamera skickade DONE tillbaka.")
