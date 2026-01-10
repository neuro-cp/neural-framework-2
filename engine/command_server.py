from __future__ import annotations
import socket
import threading
from typing import Any


def start_command_server(runtime, host="127.0.0.1", port=5557):
    def handle_command(cmd: str) -> str:
        parts = cmd.strip().split()
        if not parts:
            return "ERROR: empty command"

        op = parts[0].lower()

        # ----------------------------
        # POKE
        # ----------------------------
        if op == "poke":
            if len(parts) < 3:
                return "ERROR: poke <region> <magnitude>"
            region = parts[1]
            try:
                mag = float(parts[2])
            except ValueError:
                return "ERROR: magnitude must be float"
            runtime.inject_stimulus(region_id=region, magnitude=mag)
            return f"OK poke {region} {mag}"

        # ----------------------------
        # STATS
        # ----------------------------
        if op == "stats":
            if len(parts) < 2:
                return "ERROR: stats <region>"
            region = parts[1]
            return runtime.stats(region)

        # ----------------------------
        # TOP
        # ----------------------------
        if op == "top":
            if len(parts) < 3:
                return "ERROR: top <region> <N>"
            region = parts[1]
            try:
                n = int(parts[2])
            except ValueError:
                return "ERROR: N must be int"
            return runtime.top(region, n)

        return "Unknown command."

    def server_loop():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen(5)
            print(f"[CMD] Listening on {host}:{port}")

            while True:
                conn, _ = s.accept()
                with conn:
                    try:
                        data = conn.recv(4096)
                        if not data:
                            continue
                        cmd = data.decode("utf-8").strip()
                        result = handle_command(cmd)
                    except Exception as e:
                        result = f"ERROR: {e}"
                    conn.sendall((result + "\n").encode("utf-8"))

    thread = threading.Thread(target=server_loop, daemon=True)
    thread.start()
