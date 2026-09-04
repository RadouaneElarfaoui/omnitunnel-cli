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
import readline
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

from src.paths import PROJECT_DIR as BASE_DIR, CONFIG_PATH, CONFIG_EXAMPLE_PATH, SAVED_CONFIGS_DIR

MODE_NAMES = {
    '0': 'SSH (direct)',
    '1': 'HTTP → SSH',
    '2': 'TLS → SSH',
    '3': 'TLS → HTTP → SSH (https)',
    'v2ray': 'V2Ray / Sing-Box'
}

# ---- selection status sentinels ----------------------------------------
STATUS_BREAK = 'break'
STATUS_STAY = 'stay'


# ---- clean action wrappers (replaces duct-tape lambda: (fn(), STATUS_X)[1]) ----
def stay_after(fn):
    """Wrap fn so menu stays: fn(); return STAY."""
    def _w():
        fn()
        return STATUS_STAY
    return _w


def break_after(fn):
    """Wrap fn so menu exits: fn(); return BREAK."""
    def _w():
        fn()
        return STATUS_BREAK
    return _w


def input_editable(prompt, default):
    """Prompt with default pre-filled for in-place editing (readline).

    Enter keeps default without rewrite.
    """
    default = default if default is not None else ""
    try:
        def _hook():
            readline.insert_text(default)
        readline.set_startup_hook(_hook)
        try:
            return input(prompt)
        finally:
            readline.set_startup_hook(None)
    except Exception:
        val = input(f"{prompt}[{default}]: ").strip()
        return val if val != "" else default


def status_snapshot(config):
    """Single source for Current Configuration lines — used by print and Edit."""
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
    return {
        'mode': mode,
        'mode_name': get_mode_name(mode),
        'engine_mode': engine_mode,
        'engine_label': engine_label,
        'sb_log_level': sb_log_level,
        'ssh_host': ssh_host,
        'ssh_port': ssh_port,
        'ssh_user': ssh_user,
        'ssh_compress': ssh_compress,
        'ssh_auth': ssh_auth,
        'proxy_ip': proxy_ip,
        'proxy_port': proxy_port,
        'sni_server': sni_server,
        'payload': payload,
    }


def frame():
    """Clear and show header — replaces ad-hoc _frame() duplicates."""
    clear_screen()
    show_header()


def is_root():
    return os.geteuid() == 0


def run_as_root(cmd):
    if is_root():
        return subprocess.run(cmd)
    return subprocess.run(["sudo", *cmd])


def ensure_saved_configs_dir():
    if not os.path.exists(SAVED_CONFIGS_DIR):
        try:
            os.makedirs(SAVED_CONFIGS_DIR, exist_ok=True)
            try:
                os.chmod(SAVED_CONFIGS_DIR, 0o777)
                # also ensure parent cfgs is 777
                os.chmod(os.path.dirname(SAVED_CONFIGS_DIR), 0o777)
            except Exception:
                pass
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
    s = status_snapshot(config)
    print(f"\n{C_BOLD}Current Configuration:{C_RESET}")
    print(f"  {C_BOLD}Connection Mode:{C_RESET} {C_GREEN}{s['mode_name']}{C_RESET}")
    print(f"  {C_BOLD}SSH Server:{C_RESET}      {C_YELLOW}{s['ssh_host']}:{s['ssh_port']}{C_RESET} ({s['ssh_user']})")
    print(f"  {C_BOLD}SSH Auth Method:{C_RESET} {C_YELLOW}{s['ssh_auth']}{C_RESET} | {C_BOLD}Compression:{C_RESET} {C_YELLOW}{s['ssh_compress']}{C_RESET}")
    print(f"  {C_BOLD}Proxy Server:{C_RESET}    {C_YELLOW}{s['proxy_ip']}:{s['proxy_port']}{C_RESET}")
    print(f"  {C_BOLD}Payload:{C_RESET}         {C_YELLOW}{s['payload']}{C_RESET}")
    print(f"  {C_BOLD}SNI Host:{C_RESET}        {C_YELLOW}{s['sni_server']}{C_RESET}")
    print(f"  {C_BOLD}VPN Engine:{C_RESET}        {C_CYAN}{s['engine_label']}{C_RESET}")
    print(f"  {C_BOLD}Sing-Box Log Level:{C_RESET} {C_CYAN}{s['sb_log_level']}{C_RESET}")
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


def _resolve_label(opt):
    """Return display label; if opt[1] is callable, call it for live values."""
    lab = opt[1]
    return lab() if callable(lab) else lab


def _pick_arrows(render, options, start=0):
    """Loop in raw mode; return (chosen_key, highlight).

    highlight is preserved across calls so the caller can remember the row.
    render(i) redraws the full frame with the given highlighted index."""
    highlight = start % len(options) if options else 0
    while True:
        render(highlight)
        k = read_key_raw()
        if k == 'UP':
            highlight = (highlight - 1) % len(options)
        elif k == 'DOWN':
            highlight = (highlight + 1) % len(options)
        elif k in ('RIGHT', 'ENTER'):
            return options[highlight][0], highlight
        elif k in ('LEFT', 'ESC'):
            # Treat Esc / Left as "Back" if a Back option exists
            for idx, o in enumerate(options):
                if o[0].upper() == 'B':
                    return o[0], idx
            continue
        elif k in (None,):
            continue
        elif isinstance(k, str) and len(k) == 1:
            kk = k.upper()
            for idx, o in enumerate(options):
                if o[0] == kk:
                    return kk, idx


def _pick_number(options):
    try:
        return input(f"\nSelect an option: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        return None


def run_menu(title, options, status_render=None, mode='number'):
    """Select menu over an ordered list of (key, label, action).

    label may be a string or a zero-arg callable returning a string — useful
    for live config previews that update after each edit (inline cycling).
    action may return STATUS_BREAK to exit the loop.
    mode: 'number' (blocking input) or 'arrows' (raw arrow keys + numbers).
    Arrow mode now remembers the highlighted row when an action returns
    STATUS_STAY, fixing the "selection resets to top" annoyance. LEFT/ESC
    also maps to Back when a 'B' option exists.
    """
    highlight = 0

    def render(hl):
        clear_screen()
        show_header()
        if title:
            print(f"\n{C_BOLD}{title}{C_RESET}")
        if status_render:
            status_render()
        if mode == 'arrows':
            print(f"  {C_CYAN}↑↓ navigate · Enter/→ select · ←/Esc back · or type a number{C_RESET}")
            for i, opt in enumerate(options):
                lab = _resolve_label(opt)
                if i == hl:
                    print(f"  {C_REVERSE}[{opt[0]}] {lab}{C_RESET}")
                else:
                    print(f"  [{opt[0]}] {lab}")
        else:
            for opt in options:
                lab = _resolve_label(opt)
                print(f"  [{C_GREEN}{opt[0]}{C_RESET}] {lab}")

    while True:
        if mode == 'arrows':
            key, highlight = _pick_arrows(render, options, start=highlight)
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
