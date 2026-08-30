#!/usr/bin/env python3
import os
import sys
import json
import configparser
import subprocess
import shutil
import getpass
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

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfgs', 'settings.ini')
SAVED_CONFIGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfgs', 'saved')

MODE_NAMES = {
    '0': 'Direct SSH',
    '1': 'Payload Only',
    '2': 'SNI Only',
    '3': 'Payload + SNI',
    'v2ray': 'V2Ray / Xray / Sing-Box Profile'
}

def ensure_saved_configs_dir():
    if not os.path.exists(SAVED_CONFIGS_DIR):
        try:
            os.makedirs(SAVED_CONFIGS_DIR)
        except Exception as e:
            print(f"{C_RED}Error creating configurations directory: {e}{C_RESET}")

def clean_filename(filename):
    return "".join(c for c in filename if c.isalnum() or c in ('-', '_')).strip()

def export_omni_menu():
    ensure_saved_configs_dir()
    clear_screen()
    show_header()
    print(f"\n{C_BOLD}Export Profile to .ot File:{C_RESET}")
    print(f"  [{C_GREEN}1{C_RESET}] Export Current Active Configuration")
    print(f"  [{C_GREEN}2{C_RESET}] Export a Saved Profile from Library")
    print(f"  [{C_GREEN}B{C_RESET}] Back")

    choice = input(f"\nSelect an option: ").strip().upper()
    if choice == 'B':
        return

    config_to_export = None
    default_name = "Omni_Profile"

    if choice == '1':
        config_to_export = read_config()
        default_name = "Active_Config"
    elif choice == '2':
        configs = [f[:-4] for f in os.listdir(SAVED_CONFIGS_DIR) if f.endswith('.ini')]
        if not configs:
            print(f"\n{C_YELLOW}⚠ No saved configurations found to export.{C_RESET}")
            input("\nPress Enter to continue...")
            return
        print(f"\n{C_BOLD}Select a Profile to Export:{C_RESET}")
        for idx, cfg in enumerate(configs, 1):
            print(f"  [{C_GREEN}{idx}{C_RESET}] {cfg}")
        print(f"  [{C_GREEN}B{C_RESET}] Back")
        sel = input(f"\nSelect a profile [1-{len(configs)}]: ").strip().upper()
        if sel == 'B':
            return
        try:
            idx = int(sel) - 1
            if 0 <= idx < len(configs):
                target_cfg = configs[idx]
                src_path = os.path.join(SAVED_CONFIGS_DIR, f"{target_cfg}.ini")
                parser = configparser.ConfigParser()
                parser.read(src_path)
                config_to_export = parser
                default_name = target_cfg
            else:
                print(f"\n{C_RED}✕ Invalid selection.{C_RESET}")
                input("\nPress Enter to continue...")
                return
        except Exception as e:
            print(f"\n{C_RED}✕ Error reading profile: {e}{C_RESET}")
            input("\nPress Enter to continue...")
            return
    else:
        return

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
            print(f"\n{C_YELLOW}⚠ Empty password provided, exporting unencrypted.{C_RESET}")
            password = None

    default_out = f"{name}.ot"
    out_path = input(f"Enter destination file path [{default_out}]: ").strip()
    if not out_path:
        out_path = default_out

    try:
        exported_meta = export_profile_to_omni(
            config_to_export,
            profile_name=name,
            note=note,
            password=password,
            output_path=out_path
        )
        print(f"\n{C_GREEN}✔ Profile successfully exported to '{out_path}'!{C_RESET}")
        if password:
            print(f"  {C_YELLOW}🔒 Password protection: Enabled{C_RESET}")
    except Exception as e:
        print(f"\n{C_RED}✕ Failed to export profile: {e}{C_RESET}")
    input("\nPress Enter to continue...")


def import_omni_menu():
    clear_screen()
    show_header()
    print(f"\n{C_BOLD}Import Profile from .ot File:{C_RESET}")
    file_path = input("Enter path to .ot (or .omni) file: ").strip()
    if not file_path or not os.path.exists(file_path):
        print(f"\n{C_RED}✕ File not found: '{file_path}'{C_RESET}")
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
                print(f"\n{C_RED}✕ Maximum password attempts exceeded.{C_RESET}")
                input("\nPress Enter to continue...")
                return
            password = getpass.getpass(f"\n🔒 This profile is password protected. Enter password (Attempt {attempt}/3): ").strip()
        except InvalidProfileFormatError as e:
            print(f"\n{C_RED}✕ Invalid profile format: {e}{C_RESET}")
            input("\nPress Enter to continue...")
            return
        except Exception as e:
            print(f"\n{C_RED}✕ Error importing profile: {e}{C_RESET}")
            input("\nPress Enter to continue...")
            return

    if not config_dict or not meta:
        return

    print(f"\n{C_GREEN}✔ Profile Loaded Successfully!{C_RESET}")
    print(f"  {C_BOLD}Profile Name:{C_RESET} {C_CYAN}{meta.get('profile_name')}{C_RESET}")
    if meta.get("created_at"):
        print(f"  {C_BOLD}Created At:{C_RESET}   {meta.get('created_at')}")
    if meta.get("note"):
        print(f"  {C_BOLD}Description:{C_RESET}  {meta.get('note')}")

    print(f"\n{C_BOLD}Import Destination Options:{C_RESET}")
    print(f"  [{C_GREEN}1{C_RESET}] Set as Active Configuration (overwrites settings.ini)")
    print(f"  [{C_GREEN}2{C_RESET}] Save to Profile Library")
    print(f"  [{C_GREEN}3{C_RESET}] Both (Active Config + Profile Library)")
    print(f"  [{C_GREEN}B{C_RESET}] Cancel Import")

    action = input(f"\nSelect option [1-3]: ").strip().upper()
    if action == 'B':
        print(f"\n{C_YELLOW}Import canceled.{C_RESET}")
        input("\nPress Enter to continue...")
        return

    profile_name = clean_filename(meta.get("profile_name", "Imported_Profile"))

    if action in ['1', '3']:
        try:
            save_omni_to_ini_file(config_dict, CONFIG_PATH)
            print(f"  {C_GREEN}✔ Active configuration updated!{C_RESET}")
        except Exception as e:
            print(f"  {C_RED}✕ Error setting active configuration: {e}{C_RESET}")

    if action in ['2', '3']:
        ensure_saved_configs_dir()
        custom_name = input(f"Enter profile library name [{profile_name}]: ").strip()
        if custom_name:
            profile_name = clean_filename(custom_name)
        lib_path = os.path.join(SAVED_CONFIGS_DIR, f"{profile_name}.ini")
        try:
            save_omni_to_ini_file(config_dict, lib_path)
            print(f"  {C_GREEN}✔ Profile saved to library as '{profile_name}'!{C_RESET}")
        except Exception as e:
            print(f"  {C_RED}✕ Error saving profile to library: {e}{C_RESET}")

    input("\nPress Enter to continue...")


def import_v2ray_menu():
    clear_screen()
    show_header()
    print(f"\n{C_BOLD}Import V2Ray / Xray Share Link (VLESS, VMess, Trojan, SS, Hy2):{C_RESET}\n")
    print("Paste your share URI (e.g. vless://..., vmess://..., trojan://..., ss://..., hy2://...):")
    print("(Or enter path to a text file containing the URI link)\n")

    input_str = input(f"{C_BOLD}Share Link or File Path: {C_RESET}").strip()
    if not input_str:
        print(f"\n{C_YELLOW}Import canceled.{C_RESET}")
        input("\nPress Enter to continue...")
        return

    # Check if input is a file path
    if os.path.exists(input_str):
        try:
            with open(input_str, 'r', encoding='utf-8') as f:
                input_str = f.read().strip()
        except Exception as e:
            print(f"\n{C_RED}✕ Error reading file: {e}{C_RESET}")
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

        print(f"\n{C_GREEN}✔ V2Ray/Xray Profile successfully parsed & saved to:{C_RESET}")
        print(f"  {C_CYAN}{target_path}{C_RESET}")

        activate = input("\nActivate this V2Ray profile as current connection mode now? (Y/n): ").strip().lower()
        if activate != 'n':
            config = read_config()
            if not config.has_section('mode'):
                config.add_section('mode')
            config.set('mode', 'connection_mode', 'v2ray')
            if not config.has_section('v2ray'):
                config.add_section('v2ray')
            config.set('v2ray', 'v2ray_config', target_path)
            config.set('v2ray', 'active_remark', remark)
            write_config(config)
            print(f"\n{C_GREEN}✔ Connection mode set to V2Ray Profile ({remark})!{C_RESET}")

    except Exception as e:
        print(f"\n{C_RED}✕ Error parsing V2Ray share link: {e}{C_RESET}")

    input("\nPress Enter to continue...")

def manage_configurations():
    ensure_saved_configs_dir()
    while True:
        clear_screen()
        show_header()
        print(f"\n{C_BOLD}Manage Configurations (Profiles):{C_RESET}")
        print(f"  [{C_GREEN}1{C_RESET}] Save Current Configuration")
        print(f"  [{C_GREEN}2{C_RESET}] Load/Open Configuration")
        print(f"  [{C_GREEN}3{C_RESET}] Delete Configuration")
        print(f"  [{C_GREEN}4{C_RESET}] Export Profile to .ot File")
        print(f"  [{C_GREEN}5{C_RESET}] Import Profile from .ot File")
        print(f"  [{C_GREEN}6{C_RESET}] Import V2Ray / Xray Share Link (vless, vmess, trojan, ss, hy2)")
        print(f"  [{C_GREEN}B{C_RESET}] Back to Main Menu")

        choice = input(f"\nSelect an option: ").strip().upper()
        if choice == '1':
            name = input("\nEnter name for this configuration (e.g. MyVPS): ").strip()
            name = clean_filename(name)
            if not name:
                print(f"{C_RED}✕ Invalid name.{C_RESET}")
                input("\nPress Enter to continue...")
                continue

            dest_path = os.path.join(SAVED_CONFIGS_DIR, f"{name}.ot")
            try:
                config = read_config()
                export_profile_to_omni(config, profile_name=name, output_path=dest_path)
                print(f"\n{C_GREEN}✔ Configuration saved as '{name}.ot' successfully!{C_RESET}")
            except Exception as e:
                print(f"\n{C_RED}✕ Error saving configuration: {e}{C_RESET}")
            input("\nPress Enter to continue...")

        elif choice == '2':
            ensure_saved_configs_dir()
            files = sorted(os.listdir(SAVED_CONFIGS_DIR))
            configs = [f for f in files if f.endswith(('.ot', '.omni', '.json'))]
            if not configs:
                print(f"\n{C_YELLOW}⚠ No saved configurations found.{C_RESET}")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{C_BOLD}Saved Configuration Library:{C_RESET}")
            for idx, cfg_file in enumerate(configs, 1):
                ext = os.path.splitext(cfg_file)[1].upper()
                print(f"  [{C_GREEN}{idx}{C_RESET}] {cfg_file} ({ext})")
            print(f"  [{C_GREEN}B{C_RESET}] Back")

            sel = input(f"\nSelect a configuration to load [1-{len(configs)}]: ").strip().upper()
            if sel == 'B':
                continue
            try:
                idx = int(sel) - 1
                if 0 <= idx < len(configs):
                    target_file = configs[idx]
                    src_path = os.path.join(SAVED_CONFIGS_DIR, target_file)

                    if target_file.endswith('.json'):
                        config = read_config()
                        if not config.has_section('mode'):
                            config.add_section('mode')
                        config.set('mode', 'connection_mode', 'v2ray')
                        if not config.has_section('v2ray'):
                            config.add_section('v2ray')
                        config.set('v2ray', 'v2ray_config', src_path)
                        config.set('v2ray', 'active_remark', target_file[:-5])
                        write_config(config)
                        print(f"\n{C_GREEN}✔ V2Ray/Xray Profile '{target_file[:-5]}' loaded as active!{C_RESET}")
                    elif target_file.endswith(('.ot', '.omni')):
                        config_dict, meta = import_profile_from_omni(src_path)
                        save_omni_to_ini_file(config_dict, CONFIG_PATH)
                        print(f"\n{C_GREEN}✔ Profile '{meta['profile_name']}' (.ot) loaded successfully!{C_RESET}")
                else:
                    print(f"\n{C_RED}✕ Invalid selection.{C_RESET}")
            except Exception as e:
                print(f"\n{C_RED}✕ Error loading configuration: {e}{C_RESET}")
            input("\nPress Enter to continue...")

        elif choice == '3':
            ensure_saved_configs_dir()
            files = sorted(os.listdir(SAVED_CONFIGS_DIR))
            configs = [f for f in files if f.endswith(('.ot', '.omni', '.json'))]
            if not configs:
                print(f"\n{C_YELLOW}⚠ No saved configurations found to delete.{C_RESET}")
                input("\nPress Enter to continue...")
                continue

            print(f"\n{C_BOLD}Saved Configurations (Delete):{C_RESET}")
            for idx, cfg_file in enumerate(configs, 1):
                ext = os.path.splitext(cfg_file)[1].upper()
                print(f"  [{C_GREEN}{idx}{C_RESET}] {cfg_file} ({ext})")
            print(f"  [{C_GREEN}B{C_RESET}] Back")

            sel = input(f"\nSelect a configuration to delete [1-{len(configs)}]: ").strip().upper()
            if sel == 'B':
                continue
            try:
                idx = int(sel) - 1
                if 0 <= idx < len(configs):
                    target_file = configs[idx]
                    confirm = input(f"Are you sure you want to delete '{target_file}'? (y/N): ").strip().lower()
                    if confirm == 'y':
                        file_to_del = os.path.join(SAVED_CONFIGS_DIR, target_file)
                        os.remove(file_to_del)
                        print(f"\n{C_GREEN}✔ Configuration '{target_file}' deleted successfully!{C_RESET}")
                    else:
                        print(f"\n{C_YELLOW}Deletion canceled.{C_RESET}")
                else:
                    print(f"\n{C_RED}✕ Invalid selection.{C_RESET}")
            except Exception as e:
                print(f"\n{C_RED}✕ Error deleting configuration: {e}{C_RESET}")
            input("\nPress Enter to continue...")

        elif choice == '4':
            export_omni_menu()

        elif choice == '5':
            import_omni_menu()

        elif choice == '6':
            import_v2ray_menu()

        elif choice == 'B':
            break

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def read_config():
    config = configparser.ConfigParser()
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
    engine_label = "Sing-Box (TUN - High Speed)" if engine_mode == 'singbox' else "Redsocks (Legacy)"

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
    print(f"  {C_BOLD}Connection Mode:{C_RESET} {C_GREEN}{get_mode_name(mode)}{C_RESET}")
    print(f"  {C_BOLD}SSH Server:{C_RESET}      {C_YELLOW}{ssh_host}:{ssh_port}{C_RESET} ({ssh_user})")
    print(f"  {C_BOLD}SSH Auth Method:{C_RESET} {C_YELLOW}{ssh_auth}{C_RESET} | {C_BOLD}Compression:{C_RESET} {C_YELLOW}{ssh_compress}{C_RESET}")
    print(f"  {C_BOLD}Proxy Server:{C_RESET}    {C_YELLOW}{proxy_ip}:{proxy_port}{C_RESET}")
    print(f"  {C_BOLD}Payload:{C_RESET}         {C_YELLOW}{payload}{C_RESET}")
    print(f"  {C_BOLD}SNI Host:{C_RESET}        {C_YELLOW}{sni_server}{C_RESET}")
    print(f"{C_CYAN}-----------------------------------------------------------{C_RESET}")

def edit_engine_mode(config):
    while True:
        clear_screen()
        show_header()
        curr_engine = config.get('engine', 'engine_mode', fallback='singbox')
        print(f"\n{C_BOLD}Engine & Performance Optimizations:{C_RESET}")
        print(f"  Current Engine: {C_CYAN}{curr_engine}{C_RESET}\n")
        print(f"  [{C_GREEN}1{C_RESET}] Sing-Box Engine (TUN Mode - High Performance & Fast DNS Cache)")
        print(f"  [{C_GREEN}2{C_RESET}] Redsocks Engine (Legacy Mode)")
        print(f"  [{C_GREEN}3{C_RESET}] Activate Kernel TCP BBR Optimization")
        print(f"  [{C_GREEN}B{C_RESET}] Back to Main Menu")

        choice = input(f"\nSelect an option: ").strip().upper()
        if choice == '1':
            if not config.has_section('engine'):
                config.add_section('engine')
            config.set('engine', 'engine_mode', 'singbox')
            write_config(config)
            print(f"\n{C_GREEN}✔ Engine set to Sing-Box (TUN Mode)!{C_RESET}")
            input("\nPress Enter to continue...")
            break
        elif choice == '2':
            if not config.has_section('engine'):
                config.add_section('engine')
            config.set('engine', 'engine_mode', 'redsocks')
            write_config(config)
            print(f"\n{C_GREEN}✔ Engine set to Redsocks (Legacy Mode)!{C_RESET}")
            input("\nPress Enter to continue...")
            break
        elif choice == '3':
            print(f"\n{C_YELLOW}Running TCP BBR Optimization script...{C_RESET}")
            subprocess.run(["sudo", "bash", "vpn/tcp_bbr.sh"])
            input("\nPress Enter to continue...")
        elif choice == 'B':
            break
        else:
            print(f"\n{C_RED}✕ Invalid option.{C_RESET}")
            input("\nPress Enter to retry...")

def edit_connection_mode(config):
    while True:
        clear_screen()
        show_header()
        print(f"\n{C_BOLD}Select Connection Mode:{C_RESET}")
        print(f"  [{C_GREEN}0{C_RESET}] Direct SSH")
        print(f"  [{C_GREEN}1{C_RESET}] Payload Only (HTTP Injector)")
        print(f"  [{C_GREEN}2{C_RESET}] SNI Only (SSL/TLS)")
        print(f"  [{C_GREEN}3{C_RESET}] Payload + SNI (SSL/TLS Injector)")
        print(f"  [{C_GREEN}B{C_RESET}] Back to Main Menu")

        choice = input(f"\nSelect an option: ").strip().upper()
        if choice in ['0', '1', '2', '3']:
            config.set('mode', 'connection_mode', choice)
            write_config(config)
            print(f"\n{C_GREEN}✔ Connection mode updated to: {get_mode_name(choice)}{C_RESET}")
            input("\nPress Enter to continue...")
            break
        elif choice == 'B':
            break
        else:
            print(f"\n{C_RED}✕ Invalid option. Please try again.{C_RESET}")
            input("\nPress Enter to retry...")

def edit_ssh_parameters(config):
    while True:
        clear_screen()
        show_header()
        print(f"\n{C_BOLD}Edit SSH Parameters:{C_RESET}")
        print(f"  [{C_GREEN}1{C_RESET}] Host:        {C_YELLOW}{config.get('ssh', 'host', fallback='')}{C_RESET}")
        print(f"  [{C_GREEN}2{C_RESET}] Port:        {C_YELLOW}{config.get('ssh', 'port', fallback='')}{C_RESET}")
        print(f"  [{C_GREEN}3{C_RESET}] Username:    {C_YELLOW}{config.get('ssh', 'username', fallback='')}{C_RESET}")
        print(f"  [{C_GREEN}4{C_RESET}] Password:    {C_YELLOW}{'*' * len(config.get('ssh', 'password', fallback=''))}{C_RESET}")
        print(f"  [{C_GREEN}5{C_RESET}] Auth Method: {C_YELLOW}{config.get('ssh', 'auth_methode', fallback='password')}{C_RESET}")
        print(f"  [{C_GREEN}6{C_RESET}] Compression: {C_YELLOW}{config.get('ssh', 'enable_compression', fallback='y')}{C_RESET}")
        print(f"  [{C_GREEN}B{C_RESET}] Back to Main Menu")

        choice = input(f"\nSelect an option: ").strip().upper()
        if choice == '1':
            val = input("Enter SSH Host: ").strip()
            if val:
                config.set('ssh', 'host', val)
                write_config(config)
        elif choice == '2':
            val = input("Enter SSH Port: ").strip()
            if val:
                config.set('ssh', 'port', val)
                write_config(config)
        elif choice == '3':
            val = input("Enter SSH Username: ").strip()
            if val:
                config.set('ssh', 'username', val)
                write_config(config)
        elif choice == '4':
            val = input("Enter SSH Password: ").strip()
            if val:
                config.set('ssh', 'password', val)
                write_config(config)
        elif choice == '5':
            print("\nSelect Auth Method:")
            print("  [1] password")
            print("  [2] publickey")
            m_choice = input("Select choice [1-2]: ").strip()
            if m_choice == '1':
                config.set('ssh', 'auth_methode', 'password')
                write_config(config)
            elif m_choice == '2':
                config.set('ssh', 'auth_methode', 'publickey')
                write_config(config)
        elif choice == '6':
            comp = input("Enable compression? (y/n): ").strip().lower()
            if comp in ['y', 'n']:
                config.set('ssh', 'enable_compression', comp)
                write_config(config)
        elif choice == 'B':
            break
        else:
            print(f"\n{C_RED}✕ Invalid option.{C_RESET}")
            input("\nPress Enter to retry...")

def edit_payload_parameters(config):
    while True:
        clear_screen()
        show_header()
        print(f"\n{C_BOLD}Edit Payload & Proxy Parameters:{C_RESET}")
        print(f"  [{C_GREEN}1{C_RESET}] Proxy IP:   {C_YELLOW}{config.get('Payload', 'proxyip', fallback='')}{C_RESET}")
        print(f"  [{C_GREEN}2{C_RESET}] Proxy Port: {C_YELLOW}{config.get('Payload', 'proxyport', fallback='')}{C_RESET}")
        print(f"  [{C_GREEN}3{C_RESET}] Edit Payload Text")
        print(f"  [{C_GREEN}B{C_RESET}] Back to Main Menu")

        choice = input(f"\nSelect an option: ").strip().upper()
        if choice == '1':
            val = input("Enter Proxy IP: ").strip()
            if val:
                config.set('Payload', 'proxyip', val)
                write_config(config)
        elif choice == '2':
            val = input("Enter Proxy Port: ").strip()
            if val:
                config.set('Payload', 'proxyport', val)
                write_config(config)
        elif choice == '3':
            print(f"\nCurrent Payload:\n{C_YELLOW}{config.get('Payload', 'payload', fallback='')}{C_RESET}")
            val = input("\nEnter new payload (leave empty to keep current): ").strip()
            if val:
                config.set('Payload', 'payload', val)
                write_config(config)
        elif choice == 'B':
            break
        else:
            print(f"\n{C_RED}✕ Invalid option.{C_RESET}")
            input("\nPress Enter to retry...")

def edit_sni_parameters(config):
    while True:
        clear_screen()
        show_header()
        print(f"\n{C_BOLD}Edit SNI Parameters:{C_RESET}")
        print(f"  [{C_GREEN}1{C_RESET}] SNI Server Name: {C_YELLOW}{config.get('sni', 'server_name', fallback='')}{C_RESET}")
        print(f"  [{C_GREEN}B{C_RESET}] Back to Main Menu")

        choice = input(f"\nSelect an option: ").strip().upper()
        if choice == '1':
            val = input("Enter SNI Server Name: ").strip()
            if val:
                config.set('sni', 'server_name', val)
                write_config(config)
                print(f"\n{C_GREEN}✔ SNI updated!{C_RESET}")
                input("\nPress Enter to continue...")
                break
        elif choice == 'B':
            break
        else:
            print(f"\n{C_RED}✕ Invalid option.{C_RESET}")
            input("\nPress Enter to retry...")

def view_logs_menu():
    while True:
        clear_screen()
        show_header()
        from src.logger import SESSION_LOG_PATH, ensure_logs_dir
        ensure_logs_dir()
        print(f"\n{C_BOLD}OmniTunnel CLI - Session Logs ({SESSION_LOG_PATH}):{C_RESET}\n")

        if not os.path.exists(SESSION_LOG_PATH):
            print(f"{C_YELLOW}⚠ No log file found yet. Logs will be recorded when starting a VPN session.{C_RESET}")
        else:
            try:
                with open(SESSION_LOG_PATH, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                if not lines:
                    print(f"{C_YELLOW}⚠ Log file is empty.{C_RESET}")
                else:
                    tail_lines = lines[-40:]
                    print(f"{C_CYAN}--- Showing Last {len(tail_lines)} Log Entries ---{C_RESET}")
                    for line in tail_lines:
                        sys.stdout.write(line)
                    print(f"{C_CYAN}-------------------------------------------------{C_RESET}")
            except Exception as e:
                print(f"{C_RED}✕ Error reading log file: {e}{C_RESET}")

        print(f"\n[{C_GREEN}1{C_RESET}] Refresh Logs")
        print(f"[{C_GREEN}2{C_RESET}] Clear Log File")
        print(f"[{C_GREEN}B{C_RESET}] Back to Main Menu")

        choice = input(f"\nSelect an option: ").strip().upper()
        if choice == '1':
            continue
        elif choice == '2':
            confirm = input("Are you sure you want to clear session logs? (y/N): ").strip().lower()
            if confirm == 'y':
                try:
                    open(SESSION_LOG_PATH, 'w', encoding='utf-8').close()
                    print(f"\n{C_GREEN}✔ Session log file cleared.{C_RESET}")
                except Exception as e:
                    print(f"\n{C_RED}✕ Error clearing log file: {e}{C_RESET}")
                input("\nPress Enter to continue...")
        elif choice == 'B':
            break

def start_vpn():
    clear_screen()
    print(f"{C_GREEN}Starting VPN... (Press Ctrl+C to stop){C_RESET}\n")
    try:
        # Run runvpn.sh and stream output
        subprocess.run(["sudo", "bash", "runvpn.sh"])
    except KeyboardInterrupt:
        print(f"\n{C_RED}VPN process terminated by user.{C_RESET}")
    input("\nPress Enter to return to menu...")

def main():
    while True:
        try:
            config = read_config()
        except Exception as e:
            print(f"{C_RED}Error loading config: {e}{C_RESET}")
            sys.exit(1)

        clear_screen()
        show_header()
        print_current_status(config)

        print(f"[{C_GREEN}1{C_RESET}] Edit Connection Mode")
        print(f"[{C_GREEN}2{C_RESET}] Edit SSH Parameters")
        print(f"[{C_GREEN}3{C_RESET}] Edit Payload/Proxy Parameters")
        print(f"[{C_GREEN}4{C_RESET}] Edit SNI Server Name")
        print(f"[{C_GREEN}5{C_RESET}] Engine & Optimizations (Sing-Box / BBR)")
        print(f"[{C_GREEN}6{C_RESET}] Manage Configurations (.ot / V2Ray)")
        print(f"[{C_GREEN}7{C_RESET}] View Session Logs (logs/session.log)")
        print(f"[{C_GREEN}8{C_RESET}] RUN VPN")
        print(f"[{C_GREEN}9{C_RESET}] Exit")

        choice = input(f"\n{C_BOLD}Select an option [1-9]: {C_RESET}").strip()

        if choice == '1':
            edit_connection_mode(config)
        elif choice == '2':
            edit_ssh_parameters(config)
        elif choice == '3':
            edit_payload_parameters(config)
        elif choice == '4':
            edit_sni_parameters(config)
        elif choice == '5':
            edit_engine_mode(config)
        elif choice == '6':
            manage_configurations()
        elif choice == '7':
            view_logs_menu()
        elif choice == '8':
            start_vpn()
        elif choice == '9':
            print(f"\n{C_GREEN}Goodbye!{C_RESET}")
            break
        else:
            print(f"\n{C_RED}✕ Invalid option. Please select 1-9.{C_RESET}")
            input("\nPress Enter to retry...")

if __name__ == '__main__':
    main()
