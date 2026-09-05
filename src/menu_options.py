#!/usr/bin/env python3
import os
import sys
import json
import configparser
import getpass
import subprocess
from src.menu_common import (
    C_GREEN, C_YELLOW, C_RED, C_CYAN, C_RESET, C_BOLD,
    BASE_DIR, CONFIG_PATH, SAVED_CONFIGS_DIR,
    ensure_saved_configs_dir, clean_filename,
    read_config, write_config, get_mode_name, print_current_status,
    clear_screen, show_header, frame,
    STATUS_BREAK, STATUS_STAY, run_menu, pick_list, run_as_root,
    input_editable, status_snapshot, stay_after, break_after,
)
import functools

def _frame():
    frame()
from src.omni_profile import (
    export_profile_to_omni,
    import_profile_from_omni,
    save_omni_to_ini_file,
    dict_to_configparser,
    config_to_dict,
    InvalidPasswordError,
    InvalidProfileFormatError
)
from src.v2ray_parser import parse_v2ray_uri, generate_v2ray_singbox_config

_main_exit_flag = [False]

def _do_exit():
    _main_exit_flag[0] = True
    return STATUS_BREAK


def _set_config(section, key, val):
    """Load config, ensure the section exists, set key=val, and save."""
    config = read_config()
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, val)
    write_config(config)


# _input_prefilled is now src.menu_common.input_editable — keep alias for compat
_input_prefilled = input_editable


# ---------------------------------------------------------------------------
# Export / import
# ---------------------------------------------------------------------------
def _do_export(config_to_export, default_name):
    name = input(f"\nEnter profile name [{default_name}]: ").strip()
    if not name:
        name = default_name
    name = clean_filename(name)
    note = input("Enter optional profile description/note: ").strip()
    encrypt_choice = input("Protect this profile with a password? (y/N): ").strip().lower()
    password = None
    if encrypt_choice == 'y':
        password = getpass.getpass("Enter password for encryption: ").strip()
        if not password:
            print(f"\n{C_YELLOW}No password provided, exporting unencrypted.{C_RESET}")
            password = None
    default_out = f"{name}.ot"
    out_path = input(f"Enter destination file path [{default_out}]: ").strip()
    if not out_path:
        out_path = default_out
    try:
        export_profile_to_omni(
            config_to_export,
            profile_name=name,
            note=note,
            password=password,
            output_path=out_path
        )
        print(f"\n{C_GREEN}Profile successfully exported to '{out_path}'!{C_RESET}")
        if password:
            print(f"  {C_YELLOW}Password protection: Enabled{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}Failed to export profile: {e}{C_RESET}")
    input("\nPress Enter to continue...")


def _export_saved_library(mode):
    ensure_saved_configs_dir()
    configs = [f[:-3] for f in os.listdir(SAVED_CONFIGS_DIR) if f.endswith('.ot')]
    if not configs:
        print(f"\n{C_YELLOW}No saved configurations found to export.{C_RESET}")
        input("\nPress Enter to continue...")
        return
    choice = pick_list("Select a Profile to Export", configs, mode=mode)
    if choice is None:
        return
    try:
        src_path = os.path.join(SAVED_CONFIGS_DIR, f"{choice}.ot")
        cfg_dict, _ = import_profile_from_omni(src_path)
        _do_export(dict_to_configparser(cfg_dict), choice)
    except Exception as e:
        print(f"\n{C_RED}Error reading profile: {e}{C_RESET}")
        input("\nPress Enter to continue...")


def menu_export(mode):
    ensure_saved_configs_dir()
    configs = sorted(
        [f[:-3] for f in os.listdir(SAVED_CONFIGS_DIR) if f.endswith('.ot')]
    ) if os.path.isdir(SAVED_CONFIGS_DIR) else []
    # collapsed: single list with Current + library (was 2-option submenu)
    if not configs:
        _do_export(read_config(), "Active_Config")
        return
    items = ["▶ Current Active Configuration"] + configs
    choice = pick_list("Export Profile — pick source", items, mode=mode)
    if choice is None:
        return
    if choice == "▶ Current Active Configuration":
        _do_export(read_config(), "Active_Config")
    else:
        src_path = os.path.join(SAVED_CONFIGS_DIR, f"{choice}.ot")
        try:
            cfg_dict, _ = import_profile_from_omni(src_path)
            _do_export(dict_to_configparser(cfg_dict), choice)
        except Exception as e:
            print(f"\n{C_RED}Error reading profile: {e}{C_RESET}")
            input("\nPress Enter to continue...")


def menu_import_omni(mode):
    _frame()
    file_path = input("Enter path to .ot (or .omni) file: ").strip()
    if not file_path or not os.path.exists(file_path):
        print(f"\n{C_RED}File not found: '{file_path}'{C_RESET}")
        input("\nPress Enter to continue...")
        return

    password = None
    attempt = 0
    config_dict = None
    meta = None

    while attempt < 3:
        try:
            config_dict, meta = import_profile_from_omni(file_path, password=password)
            break
        except InvalidPasswordError:
            attempt += 1
            if attempt >= 3:
                print(f"\n{C_RED}Maximum password attempts exceeded.{C_RESET}")
                input("\nPress Enter to continue...")
                return
            password = getpass.getpass(f"\nThis profile is password protected. Enter password (Attempt {attempt}/3): ").strip()
        except InvalidProfileFormatError as e:
            print(f"\n{C_RED}Invalid profile format: {e}{C_RESET}")
            input("\nPress Enter to continue...")
            return
        except Exception as e:
            print(f"\n{C_RED}Error importing profile: {e}{C_RESET}")
            input("\nPress Enter to continue...")
            return

    if not config_dict or not meta:
        return

    _frame()
    print(f"\n{C_GREEN}Profile Loaded Successfully!{C_RESET}")
    print(f"  {C_BOLD}Profile Name:{C_RESET} {C_CYAN}{meta.get('profile_name')}{C_RESET}")
    if meta.get("created_at"):
        print(f"  {C_BOLD}Created At:{C_RESET}   {meta.get('created_at')}")
    if meta.get("note"):
        print(f"  {C_BOLD}Description:{C_RESET}  {meta.get('note')}")

    options = [
        ('1', 'Set as Active Configuration (overwrites active.ot)', break_after(lambda: _import_set_active(config_dict))),
        ('2', 'Save to Profile Library', break_after(lambda: _import_save_library(config_dict, meta))),
        ('3', 'Both (Active Config + Profile Library)', break_after(lambda: _import_both(config_dict, meta))),
        ('B', 'Cancel Import', STATUS_BREAK),
    ]
    run_menu("Import Destination Options", options, mode=mode)


def _import_set_active(config_dict):
    try:
        write_config(dict_to_configparser(config_dict))
        print(f"  {C_GREEN}Active configuration updated!{C_RESET}")
    except Exception as e:
        print(f"  {C_RED}Error setting active configuration: {e}{C_RESET}")
    input("\nPress Enter to continue...")


def _import_save_library(config_dict, meta):
    ensure_saved_configs_dir()
    profile_name = clean_filename(meta.get("profile_name", "Imported_Profile"))
    custom_name = input(f"Enter profile library name [{profile_name}]: ").strip()
    if custom_name:
        profile_name = clean_filename(custom_name)
    lib_path = os.path.join(SAVED_CONFIGS_DIR, f"{profile_name}.ot")
    try:
        export_profile_to_omni(dict_to_configparser(config_dict), profile_name=profile_name, output_path=lib_path)
        print(f"  {C_GREEN}Profile saved to library as '{profile_name}'!{C_RESET}")
    except Exception as e:
        print(f"  {C_RED}Error saving profile to library: {e}{C_RESET}")
    input("\nPress Enter to continue...")


def _import_both(config_dict, meta):
    _import_set_active(config_dict)
    _import_save_library(config_dict, meta)


def menu_import_v2ray(mode):
    _frame()
    print(f"\n{C_BOLD}Import V2Ray / Xray Share Link (VLESS, VMess, Trojan, SS, Hy2):{C_RESET}\n")
    print("Paste your share URI (e.g. vless://..., vmess://..., trojan://..., ss://..., hy2://...):")
    print("(Or enter path to a text file containing the URI link)\n")

    input_str = input(f"{C_BOLD}Share Link or File Path: {C_RESET}").strip()
    if not input_str:
        print(f"\n{C_YELLOW}Import canceled.{C_RESET}")
        input("\nPress Enter to continue...")
        return

    if os.path.exists(input_str):
        try:
            with open(input_str, 'r', encoding='utf-8') as f:
                input_str = f.read().strip()
        except Exception as e:
            print(f"\n{C_RED}Error reading file: {e}{C_RESET}")
            input("\nPress Enter to continue...")
            return

    try:
        outbound, remark = parse_v2ray_uri(input_str)
        sb_cfg = generate_v2ray_singbox_config(outbound)

        clean_remark = "".join([c for c in remark if c.isalnum() or c in ('-', '_')]).strip() or "v2ray_profile"
        ensure_saved_configs_dir()
        target_path = os.path.join(SAVED_CONFIGS_DIR, f"{clean_remark}.json")

        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(sb_cfg, f, ensure_ascii=False, indent=2)

        print(f"\n{C_GREEN}V2Ray/Xray Profile successfully parsed & saved to:{C_RESET}")
        print(f"  {C_CYAN}{target_path}{C_RESET}")

        activate = input("\nActivate this V2Ray profile as current connection mode now? (Y/n): ").strip().lower()
        if activate != 'n':
            _set_config('mode', 'connection_mode', 'v2ray')
            _set_config('v2ray', 'v2ray_config', target_path)
            _set_config('v2ray', 'active_remark', remark)
            print(f"\n{C_GREEN}Connection mode set to V2Ray Profile ({remark})!{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}Error parsing V2Ray share link: {e}{C_RESET}")
    input("\nPress Enter to continue...")


# ---------------------------------------------------------------------------
# Manage configurations
# ---------------------------------------------------------------------------
def _save_config():
    name = input("\nEnter name for this configuration (e.g. MyVPS): ").strip()
    name = clean_filename(name)
    if not name:
        print(f"{C_RED}Invalid name.{C_RESET}")
        input("\nPress Enter to continue...")
        return
    dest_path = os.path.join(SAVED_CONFIGS_DIR, f"{name}.ot")
    try:
        config = read_config()
        export_profile_to_omni(config, profile_name=name, output_path=dest_path)
        print(f"\n{C_GREEN}Configuration saved as '{name}.ot' successfully!{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}Error saving configuration: {e}{C_RESET}")
    input("\nPress Enter to continue...")


def _open_saved_folder():
    ensure_saved_configs_dir()
    try:
        subprocess.Popen(
            ["xdg-open", SAVED_CONFIGS_DIR],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True
        )
    except FileNotFoundError:
        print(f"\n{C_YELLOW}xdg-open not found — folder: {SAVED_CONFIGS_DIR}{C_RESET}")
        input("\nPress Enter to continue...")
    except Exception as e:
        print(f"\n{C_RED}Failed to open folder: {e}{C_RESET}")
        input("\nPress Enter to continue...")


def _load_config(mode, silent=False):
    ensure_saved_configs_dir()
    configs = sorted([f for f in os.listdir(SAVED_CONFIGS_DIR) if f.endswith(('.ot', '.json'))]) if os.path.isdir(SAVED_CONFIGS_DIR) else []
    if not configs:
        print(f"\n{C_YELLOW}No saved configurations found.{C_RESET}")
        input("\nPress Enter to continue...")
        return
    open_label = "📂 Open Folder"
    while True:
        items = [open_label] + configs
        choice = pick_list("Saved Configuration Library", items, mode=mode)
        if choice is None:
            return
        if choice == open_label:
            _open_saved_folder()
            # loop back to list without leaving menu
            continue
        target_file = choice
        src_path = os.path.join(SAVED_CONFIGS_DIR, target_file)
        try:
            if target_file.endswith('.json'):
                _set_config('mode', 'connection_mode', 'v2ray')
                _set_config('v2ray', 'v2ray_config', src_path)
                _set_config('v2ray', 'active_remark', target_file[:-5])
                if not silent:
                    print(f"\n{C_GREEN}V2Ray/Xray Profile '{target_file[:-5]}' loaded as active!{C_RESET}")
            elif target_file.endswith('.ot'):
                config_dict, meta = import_profile_from_omni(src_path)
                write_config(dict_to_configparser(config_dict))
                if not silent:
                    print(f"\n{C_GREEN}Profile '{meta['profile_name']}' (.ot) loaded successfully!{C_RESET}")
        except Exception as e:
            print(f"\n{C_RED}Error loading configuration: {e}{C_RESET}")
            input("\nPress Enter to continue...")
            return
        if not silent:
            input("\nPress Enter to continue...")
        return


def _delete_config(mode):
    ensure_saved_configs_dir()
    files = sorted(os.listdir(SAVED_CONFIGS_DIR))
    configs = [f for f in files if f.endswith(('.ot', '.json'))]
    if not configs:
        print(f"\n{C_YELLOW}No saved configurations found to delete.{C_RESET}")
        input("\nPress Enter to continue...")
        return
    choice = pick_list("Saved Configurations (Delete)", configs, mode=mode)
    if choice is None:
        return
    target_file = choice
    try:
        confirm = input(f"Are you sure you want to delete '{target_file}'? (y/N): ").strip().lower()
        if confirm == 'y':
            os.remove(os.path.join(SAVED_CONFIGS_DIR, target_file))
            print(f"\n{C_GREEN}Configuration '{target_file}' deleted successfully!{C_RESET}")
        else:
            print(f"\n{C_YELLOW}Deletion canceled.{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}Error deleting configuration: {e}{C_RESET}")
    input("\nPress Enter to continue...")


def menu_manage_configs(mode):
    """Simplified grouping: Save/Load/Delete together, Import/Export together.
    Keeps 6 items but with clearer grouping and ← Back; highlight is now
    remembered so you don't lose your row after an action returns."""
    ensure_saved_configs_dir()
    options = [
        ('1', 'Save Current Configuration', stay_after(_save_config)),
        ('2', 'Load / Open Configuration', stay_after(lambda: _load_config(mode))),
        ('3', 'Delete Configuration', stay_after(lambda: _delete_config(mode))),
        ('4', 'Export Profile to .ot File', stay_after(lambda: menu_export(mode))),
        ('5', 'Import Profile from .ot File', stay_after(lambda: menu_import_omni(mode))),
        ('6', 'Import V2Ray / Xray Share Link (vless, vmess, trojan, ss, hy2)', stay_after(lambda: menu_import_v2ray(mode))),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Profiles  —  manage saved configurations", options, mode=mode)


# ---------------------------------------------------------------------------
# Edit menus
# ---------------------------------------------------------------------------
def menu_edit_connection_mode(mode):
    def _lab(key, label):
        def _fn():
            cur = read_config().get('mode', 'connection_mode', fallback='0')
            mark = f" {C_GREEN}● current{C_RESET}" if cur == key else ""
            return f"{label}{mark}"
        return _fn

    options = [
        ('0', _lab('0', 'SSH (direct)'), break_after(functools.partial(_set_mode, '0'))),
        ('1', _lab('1', 'HTTP → SSH'), break_after(functools.partial(_set_mode, '1'))),
        ('2', _lab('2', 'TLS → SSH'), break_after(functools.partial(_set_mode, '2'))),
        ('3', _lab('3', 'TLS → HTTP → SSH (https)'), break_after(functools.partial(_set_mode, '3'))),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Select Connection Mode  —  ● marks active", options, mode=mode)


def _set_mode(mode_val):
    _set_config('mode', 'connection_mode', mode_val)


def menu_edit_ssh(mode):
    """Inline cycling menu — each visible line is the selectable row.

    Arrow keys move directly over the config values; no duplicate
    status block + option list. Labels are live callables so the value
    refreshes after each edit without leaving the menu.
    """
    def lab_host():
        v = status_snapshot(read_config())['ssh_host']
        return f"Host         {C_YELLOW}{v or '—'}{C_RESET}"

    def lab_port():
        v = status_snapshot(read_config())['ssh_port']
        return f"Port         {C_YELLOW}{v or '—'}{C_RESET}"

    def lab_user():
        v = status_snapshot(read_config())['ssh_user']
        return f"Username     {C_YELLOW}{v or '—'}{C_RESET}"

    def lab_pass():
        v = read_config().get('ssh', 'password', fallback='')
        masked = '*' * len(v) if v else '—'
        return f"Password     {C_YELLOW}{masked}{C_RESET}"

    def lab_auth():
        v = status_snapshot(read_config())['ssh_auth']
        return f"Auth Method  {C_YELLOW}{v}{C_RESET}"

    def lab_comp():
        v = status_snapshot(read_config())['ssh_compress']
        on = "enabled" if v.lower() == 'y' else "disabled"
        return f"Compression  {C_YELLOW}{on} ({v}){C_RESET}"

    options = [
        ('1', lab_host, stay_after(functools.partial(_edit_val, 'ssh', 'host', 'SSH Host'))),
        ('2', lab_port, stay_after(functools.partial(_edit_val, 'ssh', 'port', 'SSH Port'))),
        ('3', lab_user, stay_after(functools.partial(_edit_val, 'ssh', 'username', 'SSH Username'))),
        ('4', lab_pass, stay_after(functools.partial(_edit_val, 'ssh', 'password', 'SSH Password'))),
        ('5', lab_auth, stay_after(_edit_auth)),
        ('6', lab_comp, stay_after(_edit_compression)),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Edit SSH  —  ↑↓ to cycle fields, Enter to edit", options, mode=mode)


def _edit_val(section, key, label):
    cur = read_config().get(section, key, fallback='')
    # prefill with current value for in-place editing; Enter keeps it
    val = _input_prefilled(f"Edit {label}: ", cur)
    # None safety, strip comparison to decide change
    if val is None:
        return
    val = val.strip()
    if val != cur and val != "":
        _set_config(section, key, val)
    elif val == "" and cur == "":
        return
    elif val == "":
        # cleared line -> treat as keep (avoid wiping unintentionally)
        return


def _edit_proxy_inline():
    """Direct inline edit for Proxy Server (ip:port) — no submenu, editable."""
    cfg = read_config()
    cur_ip = cfg.get('Payload', 'proxyip', fallback='')
    cur_port = cfg.get('Payload', 'proxyport', fallback='')
    cur = f"{cur_ip}:{cur_port}" if cur_ip or cur_port else ""
    raw = _input_prefilled("Edit Proxy [ip:port]: ", cur).strip()
    if not raw or raw == cur:
        return
    if ':' in raw:
        ip, port = raw.split(':', 1)
        ip = ip.strip()
        port = port.strip()
        if ip:
            _set_config('Payload', 'proxyip', ip)
        if port:
            _set_config('Payload', 'proxyport', port)
    else:
        # no colon — treat as IP
        _set_config('Payload', 'proxyip', raw)
        # keep port as-is (user can edit separately if needed)


def _edit_auth():
    cur = read_config().get('ssh', 'auth_method', fallback='password')
    new = 'publickey' if cur == 'password' else 'password'
    _set_config('ssh', 'auth_method', new)


def _edit_compression():
    cur = read_config().get('ssh', 'enable_compression', fallback='y')
    new = 'n' if cur.lower() == 'y' else 'y'
    _set_config('ssh', 'enable_compression', new)


def menu_edit_payload(mode):
    def lab_proxy_ip():
        v = read_config().get('Payload', 'proxyip', fallback='')
        return f"Proxy IP     {C_YELLOW}{v or '—'}{C_RESET}"

    def lab_proxy_port():
        v = read_config().get('Payload', 'proxyport', fallback='')
        return f"Proxy Port   {C_YELLOW}{v or '—'}{C_RESET}"

    def lab_payload():
        v = read_config().get('Payload', 'payload', fallback='')
        preview = (v[:56] + '…') if len(v) > 57 else (v or '—')
        # show single-line preview; full payload shown when editing
        return f"Payload      {C_YELLOW}{preview}{C_RESET}"

    options = [
        ('1', lab_proxy_ip, stay_after(functools.partial(_edit_val, 'Payload', 'proxyip', 'Proxy IP'))),
        ('2', lab_proxy_port, stay_after(functools.partial(_edit_val, 'Payload', 'proxyport', 'Proxy Port'))),
        ('3', lab_payload, stay_after(_edit_payload_text)),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Edit Payload & Proxy  —  ↑↓ to cycle, Enter to edit", options, mode=mode)


def _edit_payload_text():
    cur = read_config().get('Payload', 'payload', fallback='')
    # show current for reference, but prefill the input line for editing
    print(f"\nCurrent Payload:\n{C_YELLOW}{cur}{C_RESET}\n")
    val = _input_prefilled("Edit Payload: ", cur).strip()
    if val and val != cur:
        _set_config('Payload', 'payload', val)


def menu_edit_sni(mode):
    def lab_sni():
        v = read_config().get('sni', 'server_name', fallback='')
        return f"SNI Host     {C_YELLOW}{v or '—'}{C_RESET}"

    def set_sni():
        cur = read_config().get('sni', 'server_name', fallback='')
        val = _input_prefilled("Edit SNI Host: ", cur).strip()
        if val and val != cur:
            _set_config('sni', 'server_name', val)
            print(f"\n{C_GREEN}SNI updated!{C_RESET}")
            input("\nPress Enter to continue...")
        return STATUS_STAY

    options = [
        ('1', lab_sni, set_sni),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Edit SNI  —  Enter to edit, ←/Esc to go back", options, mode=mode)


# ---------------------------------------------------------------------------
# Engine menu
# ---------------------------------------------------------------------------
def _set_engine(val, label):
    _set_config('engine', 'engine_mode', val)


def _toggle_engine():
    cur = read_config().get('engine', 'engine_mode', fallback='singbox')
    new = 'redsocks' if cur == 'singbox' else 'singbox'
    _set_config('engine', 'engine_mode', new)


def _run_bbr():
    print(f"\n{C_YELLOW}Running TCP BBR Optimization script...{C_RESET}")
    run_as_root(["bash", os.path.join(BASE_DIR, "vpn", "tcp_bbr.sh")])
    input("\nPress Enter to continue...")


def _log_level_menu(mode):
    def _lab(key, label):
        def _fn():
            cur = read_config().get('engine', 'singbox_log_level', fallback='warn')
            mark = f" {C_GREEN}●{C_RESET}" if cur == key else ""
            return f"{label}{mark}"
        return _fn

    options = [
        ('1', _lab('info', 'info   (verbose - good for debugging)'), break_after(functools.partial(_set_log_level, 'info'))),
        ('2', _lab('debug', 'debug  (most verbose)'), break_after(functools.partial(_set_log_level, 'debug'))),
        ('3', _lab('warn', 'warn   (default - less noise)'), break_after(functools.partial(_set_log_level, 'warn'))),
        ('4', _lab('error', 'error  (quietest)'), break_after(functools.partial(_set_log_level, 'error'))),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Sing-Box Log Level  —  ● marks active", options, mode=mode)


def _set_log_level(level):
    _set_config('engine', 'singbox_log_level', level)


def menu_edit_engine(mode):
    def lab_engine():
        v = read_config().get('engine', 'engine_mode', fallback='singbox')
        label = "Sing-Box" if v == 'singbox' else "Redsocks (Legacy)"
        return f"Engine       {C_CYAN}{label} ({v}){C_RESET}"

    def lab_log():
        v = read_config().get('engine', 'singbox_log_level', fallback='warn')
        return f"Log Level    {C_CYAN}{v}{C_RESET}"

    options = [
        ('1', lab_engine, stay_after(_toggle_engine)),
        ('2', lab_log, stay_after(functools.partial(_log_level_menu, mode))),
        ('3', 'TCP BBR Optimization (run once)', stay_after(_run_bbr)),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Engine & Performance  —  ↑↓ to cycle, Enter to change", options, mode=mode)


def _pick_engine(mode):
    """Legacy 2-option picker — kept for compat, now toggled directly."""

    opts = [
        ('1', 'Sing-Box (recommended)', break_after(functools.partial(_set_engine, 'singbox', 'Sing-Box'))),
        ('2', 'Redsocks (Legacy)', break_after(lambda: _set_engine('redsocks', 'Redsocks (Legacy Mode)'))),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Select Engine", opts, mode=mode)


# ---------------------------------------------------------------------------
# Logs / VPN
# ---------------------------------------------------------------------------
def menu_view_logs(mode):
    from src.logger import SESSION_LOG_PATH, ensure_logs_dir
    ensure_logs_dir()
    log_path = SESSION_LOG_PATH

    def render():
        print(f"  {C_BOLD}Session Log File:{C_RESET} {C_CYAN}{log_path}{C_RESET}")
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                if lines:
                    tail_lines = lines[-40:]
                    print(f"{C_CYAN}--- Showing Last {len(tail_lines)} Log Entries ---{C_RESET}")
                    for line in tail_lines:
                        sys.stdout.write(line)
                    print(f"{C_CYAN}-------------------------------------------------{C_RESET}")
                else:
                    print(f"{C_YELLOW}Log file is empty.{C_RESET}")
            except Exception as e:
                print(f"{C_RED}Error reading log file: {e}{C_RESET}")
        else:
            print(f"{C_YELLOW}No log file found yet. Logs will be recorded when starting a VPN session.{C_RESET}")

    options = [
        ('1', 'Refresh Logs', STATUS_STAY),
        ('2', 'Clear Log File', stay_after(lambda: _clear_logs(log_path))),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Session Logs", options, status_render=render, mode=mode)


def _clear_logs(log_path):
    confirm = input("Are you sure you want to clear session logs? (y/N): ").strip().lower()
    if confirm == 'y':
        try:
            open(log_path, 'w', encoding='utf-8').close()
            print(f"\n{C_GREEN}Session log file cleared.{C_RESET}")
        except Exception as e:
            print(f"\n{C_RED}Error clearing log file: {e}{C_RESET}")
        input("\nPress Enter to continue...")


def menu_start_vpn(mode):
    _frame()
    print(f"{C_GREEN}Starting VPN... (Press Ctrl+C to stop){C_RESET}\n")
    try:
        subprocess.run(["bash", os.path.join(BASE_DIR, "runvpn.sh")])
    except KeyboardInterrupt:
        print(f"\n{C_RED}VPN process terminated by user.{C_RESET}")
    input("\nPress Enter to return to menu...")


def menu_edit(mode):
    """Same layout as main menu's Current Configuration, but selectable.

    No duplication: previously Edit printed `print_current_status()` *and*
    a separate category list underneath. Now the preview lines *are* the
    menu — ↑↓ cycles the same 8 lines you see on the main screen
    (VPN Engine, Log Level, Connection Mode, SSH Server, etc.). Selecting
    a line edits that field(s) inline; highlight is remembered
    (`src/menu_common.py:173-245`). Main menu keeps the read-only overview,
    Edit is the identical layout made interactive.
    """
    # single source via status_snapshot — keeps Edit identical to print_current_status
    def lab_engine():
        return f"VPN Engine        {C_CYAN}{status_snapshot(read_config())['engine_label']}{C_RESET}"

    def lab_log():
        return f"Sing-Box Log Level {C_CYAN}{status_snapshot(read_config())['sb_log_level']}{C_RESET}"

    def lab_mode():
        return f"Connection Mode   {C_GREEN}{status_snapshot(read_config())['mode_name']}{C_RESET}"

    def lab_ssh_server():
        s = status_snapshot(read_config())
        return f"SSH Server        {C_YELLOW}{s['ssh_host']}:{s['ssh_port']}{C_RESET} ({s['ssh_user']})"

    def lab_ssh_auth():
        s = status_snapshot(read_config())
        return f"SSH Auth Method   {C_YELLOW}{s['ssh_auth']}{C_RESET} | Compression: {C_YELLOW}{s['ssh_compress']}{C_RESET}"

    def lab_proxy():
        s = status_snapshot(read_config())
        return f"Proxy Server      {C_YELLOW}{s['proxy_ip']}:{s['proxy_port']}{C_RESET}"

    def lab_payload():
        v = status_snapshot(read_config())['payload']
        preview = v if len(v) <= 56 else v[:53] + '…'
        return f"Payload           {C_YELLOW}{preview}{C_RESET}"

    def lab_sni():
        return f"SNI Host          {C_YELLOW}{status_snapshot(read_config())['sni_server']}{C_RESET}"

    # Actions: each line edits the underlying field(s); composite lines
    # open the focused inline submenu so you still cycle the same preview.
    # VPN Engine / Log Level at bottom (rarely changed) — mirrors
    # print_current_status order in src/menu_common.py:105.
    options = [
        ('1', lab_mode,       stay_after(functools.partial(menu_edit_connection_mode, mode))),
        ('2', lab_ssh_server, stay_after(functools.partial(menu_edit_ssh, mode))),
        ('3', lab_ssh_auth,   stay_after(functools.partial(menu_edit_ssh, mode))),
        ('4', lab_proxy,      stay_after(_edit_proxy_inline)),
        ('5', lab_payload,    stay_after(_edit_payload_text)),
        ('6', lab_sni,        stay_after(functools.partial(_edit_val, 'sni', 'server_name', 'SNI Host'))),
        ('7', lab_engine,     stay_after(functools.partial(menu_edit_engine, mode))),
        ('8', lab_log,        stay_after(functools.partial(_log_level_menu, mode))),
        ('B', '← Back', STATUS_BREAK),
    ]

    run_menu("Current Configuration", options, mode=mode)


def menu_edit_grouped(mode):
    """Legacy grouped Edit (kept for compatibility / tests).

    Shows 5 categories with inline previews. Prefer the flat `menu_edit`
    above which has no duplication and no extra drill-down.
    """
    def lab_mode():
        m = read_config().get('mode', 'connection_mode', fallback='0')
        return f"Connection Mode   {C_GREEN}{get_mode_name(m)}{C_RESET}"

    def lab_ssh():
        c = read_config()
        h = c.get('ssh', 'host', fallback='—') or '—'
        p = c.get('ssh', 'port', fallback='—') or '—'
        u = c.get('ssh', 'username', fallback='—') or '—'
        return f"SSH               {C_YELLOW}{h}:{p} ({u}){C_RESET}"

    def lab_payload():
        c = read_config()
        ip = c.get('Payload', 'proxyip', fallback='—') or '—'
        port = c.get('Payload', 'proxyport', fallback='—') or '—'
        return f"Payload / Proxy   {C_YELLOW}{ip}:{port}{C_RESET}"

    def lab_sni():
        v = read_config().get('sni', 'server_name', fallback='—') or '—'
        return f"SNI               {C_YELLOW}{v}{C_RESET}"

    def lab_engine():
        c = read_config()
        eng = c.get('engine', 'engine_mode', fallback='singbox')
        lvl = c.get('engine', 'singbox_log_level', fallback='warn')
        label = "Sing-Box" if eng == 'singbox' else "Redsocks"
        return f"Engine            {C_CYAN}{label} / log:{lvl}{C_RESET}"

    options = [
        ('1', lab_mode, stay_after(functools.partial(menu_edit_connection_mode, mode))),
        ('2', lab_ssh, stay_after(functools.partial(menu_edit_ssh, mode))),
        ('3', lab_payload, stay_after(functools.partial(menu_edit_payload, mode))),
        ('4', lab_sni, stay_after(functools.partial(menu_edit_sni, mode))),
        ('5', lab_engine, stay_after(functools.partial(menu_edit_engine, mode))),
        ('B', '← Back', STATUS_BREAK),
    ]
    run_menu("Edit (grouped) —  ↑↓ to cycle categories, Enter to edit", options, mode=mode)


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------
def menu_main(mode):
    while True:
        options = [
            ('1', 'Run VPN', stay_after(lambda: menu_start_vpn(mode))),
            ('2', 'Edit', stay_after(lambda: menu_edit(mode))),
            ('3', 'Load', stay_after(lambda: _load_config(mode, silent=True))),
            ('4', 'Profiles', stay_after(lambda: menu_manage_configs(mode))),
            ('5', 'Logs', stay_after(lambda: menu_view_logs(mode))),
            ('6', 'Exit', _do_exit),
        ]

        def render():
            print_current_status(read_config())

        run_menu(None, options, status_render=render, mode=mode)
        if _main_exit_flag[0]:
            print(f"\n{C_GREEN}Goodbye!{C_RESET}")
            break


