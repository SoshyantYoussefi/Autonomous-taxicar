#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tcp_streamer.py
Enkel TCP-streamer för JPEG-ramar (eller andra bytes).
Protokoll: [4 byte big-endian längd] + payload

- En klient åt gången (låg latens, droppar backlog).
- Trådsäker push_jpeg() från din kameraloop.
- start()/stop() eller använd som context manager.
"""

from __future__ import annotations
import socket
import struct
import threading
import time
from typing import Optional


class FrameTCPStreamer:
    def __init__(self, host: str = "0.0.0.0", port: int = 6000, listen_backlog: int = 1):
        self.host = host
        self.port = port
        self.listen_backlog = listen_backlog

        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((self.host, self.port))
        self._srv.listen(self.listen_backlog)
        self._srv.settimeout(1.0)

        self._client: Optional[socket.socket] = None
        self._client_lock = threading.Lock()

        self._latest: Optional[bytes] = None
        self._latest_lock = threading.Lock()

        self._stop = threading.Event()
        self._th_accept = threading.Thread(target=self._accept_loop, daemon=True)
        self._th_send = threading.Thread(target=self._send_loop, daemon=True)

    # -------- lifecycle --------
    def start(self) -> None:
        print(f"[TCP] Lyssnar på {self.host}:{self.port} …")
        self._th_accept.start()
        self._th_send.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._srv.close()
        except Exception:
            pass
        with self._client_lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None

    def __enter__(self) -> "FrameTCPStreamer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    # -------- public API --------
    def push_jpeg(self, data: bytes) -> None:
        """
        Lagra senaste JPEG-ram (bytes). Droppar tidigare oskickade för låg latens.
        Anropa detta i din kameraloop när du har encodat en bild.
        """
        with self._latest_lock:
            self._latest = data

    def has_client(self) -> bool:
        with self._client_lock:
            return self._client is not None

    # -------- internal loops --------
    def _accept_loop(self) -> None:
        while not self._stop.is_set():
            try:
                conn, addr = self._srv.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with self._client_lock:
                    if self._client:
                        try:
                            self._client.close()
                        except Exception:
                            pass
                    self._client = conn
                print(f"[TCP] Klient ansluten: {addr}")
            except socket.timeout:
                continue
            except OSError:
                break

    def _send_loop(self) -> None:
        pack = struct.pack
        while not self._stop.is_set():
            # Hämta ev. klient
            with self._client_lock:
                cli = self._client

            if not cli:
                time.sleep(0.01)
                continue

            # Plocka senaste frame atomärt
            with self._latest_lock:
                payload = self._latest
                self._latest = None

            if payload is None:
                time.sleep(0.002)
                continue

            try:
                cli.sendall(pack("!I", len(payload)))
                cli.sendall(payload)
            except (BrokenPipeError, ConnectionResetError, OSError):
                print("[TCP] Klient frånkopplad.")
                with self._client_lock:
                    try:
                        if self._client:
                            self._client.close()
                    except Exception:
                        pass
                    self._client = None
