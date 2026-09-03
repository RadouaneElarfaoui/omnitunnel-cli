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
    clear_screen, show_header,
    STATUS_BREAK, STATUS_STAY, run_menu, pick_list, run_as_root,
)

def _frame():
    clear_screen()
    show_header()
from src.omni_profile import (
    export_profile_to_omni,
    import_profile_from_omni,
    save_omni_to_ini_file,
    InvalidPasswordError,
    InvalidProfileFormatError
)
from src.v2ray_parser import parse_v2ray_uri, generate_v2ray_singbox_config

_main_exit_flag = [False]


def _set_config(section, key, val):
    """Load config, ensure the section exists, set key=val, and save."""
    config = read_config()
    if not config.has_section(section):
        config.add_section(section)
    config.set(section, key, val)
    write_config(config)


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
    configs = [f[:-4] for f in os.listdir(SAVED_CONFIGS_DIR) if f.endswith('.ini')]
    if not configs:
        print(f"\n{C_YELLOW}No saved configurations found to export.{C_RESET}")
        input("\nPress Enter to continue...")
        return
    choice = pick_list("Select a Profile to Export", configs, mode=mode)
    if choice is None:
        return
    try:
        target_cfg = choice
        src_path = os.path.join(SAVED_CONFIGS_DIR, f"{target_cfg}.ini")
        parser = configparser.ConfigParser()
        parser.read(src_path)
        _do_export(parser, target_cfg)
    except Exception as e:
        print(f"\n{C_RED}Error reading profile: {e}{C_RESET}")
        input("\nPress Enter to continue...")


def menu_export(mode):
    configs = [
        f[:-4] for f in os.listdir(SAVED_CONFIGS_DIR)
        if f.endswith('.ini')
    ] if os.path.isdir(SAVED_CONFIGS_DIR) else []
    has_lib = bool(configs)
    options = [('1', 'Export Current Active Configuration', lambda: (_do_export(read_config(), "Active_Config"), STATUS_BREAK)[1])]
    if has_lib:
        options.append(('2', 'Export a Saved Profile from Library', lambda: (_export_saved_library(mode), STATUS_BREAK)[1]))
    options.append(('B', 'Back', lambda: STATUS_BREAK))
    run_menu("Export Profile to .ot File", options, mode=mode)


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
        ('1', 'Set as Active Configuration (overwrites settings.ini)', lambda: (_import_set_active(config_dict), STATUS_BREAK)[1]),
        ('2', 'Save to Profile Library', lambda: (_import_save_library(config_dict, meta), STATUS_BREAK)[1]),
        ('3', 'Both (Active Config + Profile Library)', lambda: (_import_both(config_dict, meta), STATUS_BREAK)[1]),
        ('B', 'Cancel Import', STATUS_BREAK),
    ]
    run_menu("Import Destination Options", options, mode=mode)


def _import_set_active(config_dict):
    try:
        save_omni_to_ini_file(config_dict, CONFIG_PATH)
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
    lib_path = os.path.join(SAVED_CONFIGS_DIR, f"{profile_name}.ini")
    try:
        save_omni_to_ini_file(config_dict, lib_path)
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


def _load_config(mode):
    ensure_saved_configs_dir()
    files = sorted(os.listdir(SAVED_CONFIGS_DIR))
    configs = [f for f in files if f.endswith(('.ot', '.omni', '.json'))]
    if not configs:
        print(f"\n{C_YELLOW}No saved configurations found.{C_RESET}")
        input("\nPress Enter to continue...")
        return
    choice = pick_list("Saved Configuration Library", configs, mode=mode)
    if choice is None:
        return
    target_file = choice
    src_path = os.path.join(SAVED_CONFIGS_DIR, target_file)
    try:
        if target_file.endswith('.json'):
            _set_config('mode', 'connection_mode', 'v2ray')
            _set_config('v2ray', 'v2ray_config', src_path)
            _set_config('v2ray', 'active_remark', target_file[:-5])
            print(f"\n{C_GREEN}V2Ray/Xray Profile '{target_file[:-5]}' loaded as active!{C_RESET}")
        elif target_file.endswith(('.ot', '.omni')):
            config_dict, meta = import_profile_from_omni(src_path)
            save_omni_to_ini_file(config_dict, CONFIG_PATH)
            print(f"\n{C_GREEN}Profile '{meta['profile_name']}' (.ot) loaded successfully!{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}Error loading configuration: {e}{C_RESET}")
    input("\nPress Enter to continue...")


def _delete_config(mode):
    ensure_saved_configs_dir()
    files = sorted(os.listdir(SAVED_CONFIGS_DIR))
    configs = [f for f in files if f.endswith(('.ot', '.omni', '.json'))]
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
    ensure_saved_configs_dir()
    options = [
        ('1', 'Save Current Configuration', lambda: (_save_config(), STATUS_STAY)[1]),
        ('2', 'Load/Open Configuration', lambda: (_load_config(mode), STATUS_STAY)[1]),
        ('3', 'Delete Configuration', lambda: (_delete_config(mode), STATUS_STAY)[1]),
        ('4', 'Export Profile to .ot File', lambda: (menu_export(mode), STATUS_STAY)[1]),
        ('5', 'Import Profile from .ot File', lambda: (menu_import_omni(mode), STATUS_STAY)[1]),
        ('6', 'Import V2Ray / Xray Share Link (vless, vmess, trojan, ss, hy2)', lambda: (menu_import_v2ray(mode), STATUS_STAY)[1]),
        ('B', 'Back to Main Menu', STATUS_BREAK),
    ]
    run_menu("MANAGE CONFIGURATIONS (PROFILES)", options, mode=mode)


# ---------------------------------------------------------------------------
# Edit menus
# ---------------------------------------------------------------------------
def menu_edit_connection_mode(mode):
    options = [
        ('0', 'SSH (direct)', lambda: (_set_mode('0'), STATUS_BREAK)[1]),
        ('1', 'HTTP → SSH', lambda: (_set_mode('1'), STATUS_BREAK)[1]),
        ('2', 'TLS → SSH', lambda: (_set_mode('2'), STATUS_BREAK)[1]),
        ('3', 'TLS → HTTP → SSH (https)', lambda: (_set_mode('3'), STATUS_BREAK)[1]),
        ('B', 'Back to Main Menu', STATUS_BREAK),
    ]
    run_menu("Select Connection Mode", options, mode=mode)


def _set_mode(mode_val):
    _set_config('mode', 'connection_mode', mode_val)
    print(f"\n{C_GREEN}Connection mode updated to: {get_mode_name(mode_val)}{C_RESET}")
    input("\nPress Enter to continue...")


def menu_edit_ssh(mode):
    def render():
        config = read_config()
        print(f"  {C_BOLD}Host:{C_RESET}        {C_YELLOW}{config.get('ssh', 'host', fallback='')}{C_RESET}")
        print(f"  {C_BOLD}Port:{C_RESET}        {C_YELLOW}{config.get('ssh', 'port', fallback='')}{C_RESET}")
        print(f"  {C_BOLD}Username:{C_RESET}    {C_YELLOW}{config.get('ssh', 'username', fallback='')}{C_RESET}")
        print(f"  {C_BOLD}Password:{C_RESET}    {C_YELLOW}{'*' * len(config.get('ssh', 'password', fallback=''))}{C_RESET}")
        print(f"  {C_BOLD}Auth Method:{C_RESET} {C_YELLOW}{config.get('ssh', 'auth_methode', fallback='password')}{C_RESET}")
        print(f"  {C_BOLD}Compression:{C_RESET} {C_YELLOW}{config.get('ssh', 'enable_compression', fallback='y')}{C_RESET}")

    options = [
        ('1', 'Host', lambda: (_edit_val('ssh', 'host', 'SSH Host'), STATUS_STAY)[1]),
        ('2', 'Port', lambda: (_edit_val('ssh', 'port', 'SSH Port'), STATUS_STAY)[1]),
        ('3', 'Username', lambda: (_edit_val('ssh', 'username', 'SSH Username'), STATUS_STAY)[1]),
        ('4', 'Password', lambda: (_edit_val('ssh', 'password', 'SSH Password'), STATUS_STAY)[1]),
        ('5', 'Auth Method', lambda: (_edit_auth(), STATUS_STAY)[1]),
        ('6', 'Compression', lambda: (_edit_compression(), STATUS_STAY)[1]),
        ('B', 'Back to Main Menu', STATUS_BREAK),
    ]
    run_menu("Edit SSH Parameters", options, status_render=render, mode=mode)


def _edit_val(section, key, label):
    val = input(f"Enter {label}: ").strip()
    if val:
        _set_config(section, key, val)


def _edit_auth():
    print("\nSelect Auth Method:")
    print("  [1] password")
    print("  [2] publickey")
    m_choice = input("Select choice [1-2]: ").strip()
    if m_choice == '1':
        _set_config('ssh', 'auth_methode', 'password')
    elif m_choice == '2':
        _set_config('ssh', 'auth_methode', 'publickey')


def _edit_compression():
    comp = input("Enable compression? (y/n): ").strip().lower()
    if comp in ['y', 'n']:
        _set_config('ssh', 'enable_compression', comp)


def menu_edit_payload(mode):
    def render():
        config = read_config()
        print(f"  {C_BOLD}Proxy IP:{C_RESET}   {C_YELLOW}{config.get('Payload', 'proxyip', fallback='')}{C_RESET}")
        print(f"  {C_BOLD}Proxy Port:{C_RESET} {C_YELLOW}{config.get('Payload', 'proxyport', fallback='')}{C_RESET}")

    options = [
        ('1', 'Proxy IP', lambda: (_edit_val('Payload', 'proxyip', 'Proxy IP'), STATUS_STAY)[1]),
        ('2', 'Proxy Port', lambda: (_edit_val('Payload', 'proxyport', 'Proxy Port'), STATUS_STAY)[1]),
        ('3', 'Edit Payload Text', lambda: (_edit_payload_text(), STATUS_STAY)[1]),
        ('B', 'Back to Main Menu', STATUS_BREAK),
    ]
    run_menu("Edit Payload & Proxy Parameters", options, status_render=render, mode=mode)


def _edit_payload_text():
    config = read_config()
    print(f"\nCurrent Payload:\n{C_YELLOW}{config.get('Payload', 'payload', fallback='')}{C_RESET}")
    val = input("\nEnter new payload (leave empty to keep current): ").strip()
    if val:
        _set_config('Payload', 'payload', val)


def menu_edit_sni(mode):
    def render():
        config = read_config()
        print(f"  {C_BOLD}SNI Server Name:{C_RESET} {C_YELLOW}{config.get('sni', 'server_name', fallback='')}{C_RESET}")

    def set_sni():
        val = input("Enter SNI Server Name: ").strip()
        if val:
            _set_config('sni', 'server_name', val)
            print(f"\n{C_GREEN}SNI updated!{C_RESET}")
            input("\nPress Enter to continue...")
            return STATUS_BREAK
        return STATUS_STAY

    options = [
        ('1', 'SNI Server Name', set_sni),
        ('B', 'Back to Main Menu', STATUS_BREAK),
    ]
    run_menu("Edit SNI Parameters", options, status_render=render, mode=mode)


# ---------------------------------------------------------------------------
# Engine menu
# ---------------------------------------------------------------------------
def _set_engine(val, label):
    _set_config('engine', 'engine_mode', val)
    print(f"\n{C_GREEN}Engine set to {label}!{C_RESET}")
    input("\nPress Enter to continue...")


def _run_bbr():
    print(f"\n{C_YELLOW}Running TCP BBR Optimization script...{C_RESET}")
    run_as_root(["bash", os.path.join(BASE_DIR, "vpn", "tcp_bbr.sh")])
    input("\nPress Enter to continue...")


def _log_level_menu(mode):
    def render():
        config = read_config()
        cur = config.get('engine', 'singbox_log_level', fallback='warn')
        print(f"  {C_BOLD}Sing-Box Log Level (current: {C_CYAN}{cur}{C_RESET}{C_BOLD}){C_RESET}")

    options = [
        ('1', 'info   (verbose - good for debugging)', lambda: (_set_log_level('info'), STATUS_BREAK)[1]),
        ('2', 'debug  (most verbose)', lambda: (_set_log_level('debug'), STATUS_BREAK)[1]),
        ('3', 'warn   (default - less noise)', lambda: (_set_log_level('warn'), STATUS_BREAK)[1]),
        ('4', 'error  (quietest)', lambda: (_set_log_level('error'), STATUS_BREAK)[1]),
        ('B', 'Back', STATUS_BREAK),
    ]
    run_menu("Sing-Box Log Level", options, status_render=render, mode=mode)


def _set_log_level(level):
    _set_config('engine', 'singbox_log_level', level)
    print(f"\n{C_GREEN}Sing-Box log level set to {level}{C_RESET}")
    input("\nPress Enter to continue...")


def menu_edit_engine(mode):
    def render():
        config = read_config()
        print(f"  {C_BOLD}Current Engine:{C_RESET} {C_CYAN}{config.get('engine', 'engine_mode', fallback='singbox')}{C_RESET}")
        print(f"  {C_BOLD}Current Sing-Box Log Level:{C_RESET} {C_CYAN}{config.get('engine', 'singbox_log_level', fallback='warn')}{C_RESET}")

    options = [
        ('1', 'Sing-Box Engine', lambda: (_set_engine('singbox', 'Sing-Box'), STATUS_BREAK)[1]),
        ('2', 'Redsocks Engine (Legacy Mode)', lambda: (_set_engine('redsocks', 'Redsocks (Legacy Mode)'), STATUS_BREAK)[1]),
        ('3', 'Activate Kernel TCP BBR Optimization', lambda: (_run_bbr(), STATUS_STAY)[1]),
        ('4', 'Change Sing-Box Log Level', lambda: (_log_level_menu(mode), STATUS_STAY)[1]),
        ('B', 'Back to Main Menu', STATUS_BREAK),
    ]
    run_menu("Engine & Performance Optimizations", options, status_render=render, mode=mode)


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
        ('2', 'Clear Log File', lambda: (_clear_logs(log_path), STATUS_STAY)[1]),
        ('B', 'Back to Main Menu', STATUS_BREAK),
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
    options = [
        ('1', 'Connection Mode', lambda: (menu_edit_connection_mode(mode), STATUS_STAY)[1]),
        ('2', 'SSH', lambda: (menu_edit_ssh(mode), STATUS_STAY)[1]),
        ('3', 'Payload / Proxy', lambda: (menu_edit_payload(mode), STATUS_STAY)[1]),
        ('4', 'SNI', lambda: (menu_edit_sni(mode), STATUS_STAY)[1]),
        ('5', 'Engine', lambda: (menu_edit_engine(mode), STATUS_STAY)[1]),
        ('B', 'Back', STATUS_BREAK),
    ]

    def render():
        print_current_status(read_config())

    run_menu("Edit", options, status_render=render, mode=mode)


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------
def menu_main(mode):
    while True:
        options = [
            ('1', 'Run VPN', lambda: (menu_start_vpn(mode), STATUS_STAY)[1]),
            ('2', 'Edit', lambda: (menu_edit(mode), STATUS_STAY)[1]),
            ('3', 'Profiles', lambda: (menu_manage_configs(mode), STATUS_STAY)[1]),
            ('4', 'Logs', lambda: (menu_view_logs(mode), STATUS_STAY)[1]),
            ('5', 'Exit', lambda: (_main_exit_flag.__setitem__(0, True) or STATUS_BREAK)),
        ]

        def render():
            print_current_status(read_config())

        run_menu(None, options, status_render=render, mode=mode)
        if _main_exit_flag[0]:
            print(f"\n{C_GREEN}Goodbye!{C_RESET}")
            break


