#!/usr/bin/env python3
import os
import sys
import re
import datetime

from src.paths import PROJECT_DIR, LOGS_DIR, SESSION_LOG_PATH

# Regex pattern to match ANSI escape codes (colors, formatting)
ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from text string for clean file logging."""
    if not isinstance(text, str):
        text = str(text)
    return ANSI_ESCAPE_RE.sub('', text)

def ensure_logs_dir():
    """Ensure that the logs/ directory exists."""
    if not os.path.exists(LOGS_DIR):
        try:
            os.makedirs(LOGS_DIR, exist_ok=True)
        except Exception as e:
            sys.stderr.write(f"Failed to create logs directory: {e}\n")

def write_log(tag: str, message: str, print_console: bool = True):
    """
    Write timestamped log entry to logs/session.log and stream to console.
    """
    ensure_logs_dir()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_msg = strip_ansi(message)
    file_line = f"[{now_str}] [{tag.upper()}] {clean_msg}\n"

    try:
        with open(SESSION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(file_line)
    except Exception as e:
        sys.stderr.write(f"Logging error: {e}\n")

    if print_console:
        print(f"[{now_str}] [{tag.upper()}] {message}")

def log_info(message: str, tag: str = "INFO", print_console: bool = True):
    write_log(tag, message, print_console=print_console)

def log_ssh(message: str, print_console: bool = True):
    write_log("SSH", message, print_console=print_console)

def log_singbox(message: str, print_console: bool = True):
    write_log("SINGBOX", message, print_console=print_console)

def log_tunnel(message: str, print_console: bool = True):
    write_log("TUNNEL", message, print_console=print_console)

def log_error(message: str, tag: str = "ERROR", print_console: bool = True):
    write_log(tag, message, print_console=print_console)

def log_session_start():
    """Write a new session header separator into session.log."""
    ensure_logs_dir()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = f"\n==================== OMNITUNNEL SESSION START: {now_str} ====================\n"
    try:
        with open(SESSION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(separator)
    except Exception as e:
        sys.stderr.write(f"Logging error: {e}\n")

def main():
    log_session_start()
    log_info("Logger module initialized successfully.")
    log_ssh("\033[32mSSH Connection established.\033[0m")
    log_singbox("Sing-box TUN engine active.")

if __name__ == '__main__':
    main()
