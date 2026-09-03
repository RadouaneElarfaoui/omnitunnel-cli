#!/usr/bin/env python3
import os
import sys
import json
import configparser
import subprocess
import shutil
import getpass
import termios
import tty
from src.omni_profile import (
    export_profile_to_omni,
    import_profile_from_omni,
    save_omni_to_ini_file,
    InvalidPasswordError,
    InvalidProfileFormatError
)
from src.v2ray_parser import parse_v2ray_uri, generate_v2ray_singbox_config

# Colors
C_BLUE = '\033[1;34m'
C_GREEN = '\033[1;32m'
C_YELLOW = '\033[1;33m'
C_RED = '\033[1;31m'
C_CYAN = '\033[1;36m'
C_RESET = '\033[0m'
C_BOLD = '\033[1m'
C_REVERSE = '\033[7m'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'cfgs', 'settings.ini')
CONFIG_EXAMPLE_PATH = os.path.join(BASE_DIR, 'cfgs', 'settings.ot.example')
SAVED_CONFIGS_DIR = os.path.join(BASE_DIR, 'cfgs', 'saved')

MODE_NAMES = {
    '0': 'SSH (direct)',
    '1': 'HTTP → SSH',
    '2': 'TLS → SSH',
    '3': 'HTTP → TLS → SSH',
    'v2ray': 'V2Ray / Sing-Box'
}

# ---- selection status sentinels ----------------------------------------
STATUS_BREAK = 'break'
STATUS_STAY = 'stay'


def is_root():
    return os.geteuid() == 0


def run_as_root(cmd):
    if is_root():
        return subprocess.run(cmd)
    return subprocess.run(["sudo", *cmd])


def ensure_saved_configs_dir():
    if not os.path.exists(SAVED_CONFIGS_DIR):
        try:
            os.makedirs(SAVED_CONFIGS_DIR)
        except Exception as e:
            print(f"{C_RED}Error creating configurations directory: {e}{C_RESET}")


def clean_filename(filename):
    return "".join(c for c in filename if c.isalnum() or c in ('-', '_')).strip()


def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')


def read_config():
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_PATH) and os.path.exists(CONFIG_EXAMPLE_PATH):
        try:
            cfg_dict, _ = import_profile_from_omni(CONFIG_EXAMPLE_PATH)
            save_omni_to_ini_file(cfg_dict, CONFIG_PATH)
        except Exception:
            pass
    config.read(CONFIG_PATH)
    return config


def write_config(config):
    with open(CONFIG_PATH, 'w') as configfile:
        config.write(configfile)


def get_mode_name(mode):
    return MODE_NAMES.get(mode, f"Unknown ({mode})")


def show_header():
    print(f"{C_CYAN}==========================================================={C_RESET}")
    print(f"{C_CYAN}            OMNITUNNEL CLI TERMINAL MENU                   {C_RESET}")
    print(f"{C_CYAN}==========================================================={C_RESET}")


def print_current_status(config):
    mode = config.get('mode', 'connection_mode', fallback='0')
    engine_mode = config.get('engine', 'engine_mode', fallback='singbox')
    engine_label = "Sing-Box" if engine_mode == 'singbox' else "Redsocks (Legacy)"
    sb_log_level = config.get('engine', 'singbox_log_level', fallback='warn')

    ssh_host = config.get('ssh', 'host', fallback='None')
    ssh_port = config.get('ssh', 'port', fallback='None')
    ssh_user = config.get('ssh', 'username', fallback='None')
    ssh_compress = config.get('ssh', 'enable_compression', fallback='n')
    ssh_auth = config.get('ssh', 'auth_methode', fallback='password')
    proxy_ip = config.get('Payload', 'proxyip', fallback='None')
    proxy_port = config.get('Payload', 'proxyport', fallback='None')
    sni_server = config.get('sni', 'server_name', fallback='None')
    payload = config.get('Payload', 'payload', fallback='None')

    print(f"\n{C_BOLD}Current Configuration:{C_RESET}")
    print(f"  {C_BOLD}VPN Engine:{C_RESET}        {C_CYAN}{engine_label}{C_RESET}")
    print(f"  {C_BOLD}Sing-Box Log Level:{C_RESET} {C_CYAN}{sb_log_level}{C_RESET}")
    print(f"  {C_BOLD}Connection Mode:{C_RESET} {C_GREEN}{get_mode_name(mode)}{C_RESET}")
    print(f"  {C_BOLD}SSH Server:{C_RESET}      {C_YELLOW}{ssh_host}:{ssh_port}{C_RESET} ({ssh_user})")
    print(f"  {C_BOLD}SSH Auth Method:{C_RESET} {C_YELLOW}{ssh_auth}{C_RESET} | {C_BOLD}Compression:{C_RESET} {C_YELLOW}{ssh_compress}{C_RESET}")
    print(f"  {C_BOLD}Proxy Server:{C_RESET}    {C_YELLOW}{proxy_ip}:{proxy_port}{C_RESET}")
    print(f"  {C_BOLD}Payload:{C_RESET}         {C_YELLOW}{payload}{C_RESET}")
    print(f"  {C_BOLD}SNI Host:{C_RESET}        {C_YELLOW}{sni_server}{C_RESET}")
    print(f"{C_CYAN}-----------------------------------------------------------{C_RESET}")


# ---- raw keyboard reader (single key press) -----------------------------
def read_key_raw():
    """Read a single key in raw mode. Returns a token string: an arrow name,
    'ENTER', 'ESC', a single printable char, or None on error."""
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except Exception:
        return None
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            seq = sys.stdin.read(2)
            if seq == '[A':
                return 'UP'
            elif seq == '[B':
                return 'DOWN'
            elif seq == '[C':
                return 'RIGHT'
            elif seq == '[D':
                return 'LEFT'
            elif seq == '':
                return 'ESC'
            return None
        if ch in ('\r', '\n'):
            return 'ENTER'
        if ch == '\x03':
            raise KeyboardInterrupt
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _pick_arrows(render, options):
    """Loop in raw mode; return the chosen option key. render(i) redraws the
    full frame with the given highlighted index."""
    highlight = 0
    while True:
        render(highlight)
        k = read_key_raw()
        if k == 'UP':
            highlight = (highlight - 1) % len(options)
        elif k == 'DOWN':
            highlight = (highlight + 1) % len(options)
        elif k in ('RIGHT', 'ENTER'):
            return options[highlight][0]
        elif k in ('UP', 'DOWN', None, 'ESC'):
            continue
        elif isinstance(k, str) and len(k) == 1:
            kk = k.upper()
            for o in options:
                if o[0] == kk:
                    return kk


def _pick_number(options):
    try:
        return input(f"\nSelect an option: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        return None


def run_menu(title, options, status_render=None, mode='number'):
    """Select menu over an ordered list of (key, label, action).

    action may return STATUS_BREAK to exit the loop.
    mode: 'number' (blocking input) or 'arrows' (raw arrow keys + numbers).
    """
    def render(highlight):
        clear_screen()
        show_header()
        if title:
            print(f"\n{C_BOLD}{title}{C_RESET}")
        if status_render:
            status_render()
        if mode == 'arrows':
            print(f"  {C_CYAN}↑↓ navigate · Enter select · or type a number{C_RESET}")
            for i, opt in enumerate(options):
                if i == highlight:
                    print(f"  {C_REVERSE}[{opt[0]}] {opt[1]}{C_RESET}")
                else:
                    print(f"  [{opt[0]}] {opt[1]}")
        else:
            for opt in options:
                print(f"  [{C_GREEN}{opt[0]}{C_RESET}] {opt[1]}")

    while True:
        if mode == 'arrows':
            key = _pick_arrows(render, options)
        else:
            render(0)
            key = _pick_number(options)
        if key is None:
            return
        chosen = None
        for o in options:
            if o[0] == key:
                chosen = o
                break
        if chosen is None:
            print(f"\n{C_RED}✕ Invalid option.{C_RESET}")
            input("\nPress Enter to retry...")
            continue
        action = chosen[2]
        if callable(action):
            result = action()
        else:
            result = action
        if result == STATUS_BREAK:
            return


def pick_list(title, items, mode='number'):
    """Numbered list picker over display strings. Returns the chosen item or
    None for Back."""
    result = [None]

    def make_action(item):
        def act():
            result[0] = item
            return STATUS_BREAK
        return act

    options = [(str(i), label, make_action(label)) for i, label in enumerate(items, 1)]
    options.append(('B', 'Back', lambda: STATUS_BREAK))
    run_menu(title, options, mode=mode)
    return result[0]
