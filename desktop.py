import os
import sys
import time
import socket
import threading
import webbrowser
import subprocess
import uvicorn

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.server import app

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((SERVER_HOST, port)) == 0

def find_available_port(start_port: int = 8000) -> int:
    port = start_port
    while is_port_in_use(port):
        # If it's already running our health check, we can use it
        try:
            import urllib.request, json
            req = urllib.request.Request(f"http://{SERVER_HOST}:{port}/api/health", headers={"User-Agent": "PostFinder"})
            with urllib.request.urlopen(req, timeout=0.5) as resp:
                data = json.loads(resp.read().decode())
                if data.get("service") == "PostFinder":
                    return port
        except Exception:
            pass
        port += 1
    return port

class UvicornServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        config = uvicorn.Config(app=app, host=self.host, port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True

def wait_for_server(url: str, timeout: float = 10.0) -> bool:
    import urllib.request
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False

def open_fallback_window(app_url: str):
    """Fallback if pywebview fails: launches Edge in app mode or default browser."""
    # Check Edge app mode on Windows
    edge_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe")
    ]
    edge_bin = next((p for p in edge_paths if os.path.exists(p)), None)
    
    if edge_bin:
        print("Launching desktop app window using Microsoft Edge...")
        proc = subprocess.Popen([edge_bin, f"--app={app_url}"])
        proc.wait()
    else:
        print("Opening in default browser...")
        webbrowser.open(app_url)
        # Keep process running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

def main():
    port = find_available_port(SERVER_PORT)
    app_url = f"http://{SERVER_HOST}:{port}"

    server_thread = None
    # If not already running on this port, start Uvicorn
    if not is_port_in_use(port):
        print(f"Starting PostFinder backend on {app_url}...")
        server_thread = UvicornServerThread(SERVER_HOST, port)
        server_thread.start()

        if not wait_for_server(app_url, timeout=12.0):
            print("Server failed to respond in time.")
            sys.exit(1)
    else:
        print(f"Connected to existing PostFinder backend at {app_url}")

    print("Launching native desktop application window...")
    use_webview = True
    try:
        import webview
        window = webview.create_window(
            title="PostFinder - Nearest Serviceable Post Office",
            url=app_url,
            width=1120,
            height=820,
            min_size=(820, 600),
            resizable=True
        )
        webview.start()
    except Exception as e:
        print(f"Note: pywebview native window encountered an issue: {e}")
        use_webview = False

    if not use_webview:
        open_fallback_window(app_url)

    if server_thread:
        print("Shutting down PostFinder backend...")
        server_thread.stop()

if __name__ == "__main__":
    main()
