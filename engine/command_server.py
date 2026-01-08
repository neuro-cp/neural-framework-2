from __future__ import annotations
import socket
import threading


def start_command_server(runtime, host="127.0.0.1", port=5557):
    def server_loop():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen(5)

            print(f"[CMD] Listening on {host}:{port}")

            while True:
                conn, addr = s.accept()
                with conn:
                    data = conn.recv(4096)
                    if not data:
                        continue

                    try:
                        cmd = data.decode("utf-8").strip()
                        result = runtime.apply_command(cmd)
                    except Exception as e:
                        result = f"ERROR: {e}"

                    conn.sendall((result + "\n").encode("utf-8"))

    thread = threading.Thread(target=server_loop, daemon=True)
    thread.start()
