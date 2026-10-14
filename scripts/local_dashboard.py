"""Start a static dashboard server bound only to this computer."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.error
import urllib.request


def start_dashboard(root, environment, api_url):
    """Reuse a matching local server or start one; never stop unrelated processes."""
    url = "http://localhost:8020"
    try:
        with urllib.request.urlopen(url + "/config.js", timeout=2) as response:
            config_matches = api_url.encode() in response.read()
        with urllib.request.urlopen(url, timeout=2) as response:
            page_matches = b"RescueRoute" in response.read()
        if config_matches and page_matches:
            print("Using the existing local dashboard server.")
            return None
    except (urllib.error.URLError, TimeoutError, OSError):
        pass
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 8020))
    except OSError as error:
        raise RuntimeError("Port 8020 is occupied by another server. Close that server and retry.") from error
    command = [sys.executable, "-m", "http.server", "8020", "--bind", "127.0.0.1",
               "--directory", str(Path(root) / "frontend")]
    if os.name == "nt":
        process = subprocess.Popen(command, env=environment, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        log = Path(root) / ".aws-sam" / "review" / "local-dashboard.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as stream:
            process = subprocess.Popen(command, env=environment, stdout=stream, stderr=stream, start_new_session=True)
    pid_file = Path(root) / ".aws-sam" / "review" / "local-dashboard.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(process.pid), encoding="utf-8")
    print("Started dashboard server on", url)
    return process
