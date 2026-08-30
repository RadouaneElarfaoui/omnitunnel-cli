import subprocess
import os
import signal

def handler(thread):
    try:
        cmd = subprocess.Popen(
            f"netstat -anp 2>/dev/null | grep {thread}" + " | awk '{print $7}'",
            shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, _ = cmd.communicate(timeout=5)
        for line in output.splitlines():
            parts = line.split(b'/')
            if len(parts) >= 1 and parts[0].strip().isdigit():
                pid = int(parts[0].decode().strip())
                try:
                    os.kill(pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
    except Exception:
        pass
