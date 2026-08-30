#!/usr/bin/env python3
import os
import sys
import json
import base64
import hashlib
import hmac
import datetime
import configparser
import argparse

FORMAT_VERSION = "1.0"
SOFTWARE_NAME = "OmniTunnel CLI"

class OmniProfileError(Exception):
    """Base exception for Omni Profile operations."""
    pass

class InvalidPasswordError(OmniProfileError):
    """Raised when password decryption fails."""
    pass

class InvalidProfileFormatError(OmniProfileError):
    """Raised when profile format is invalid or corrupted."""
    pass

def _derive_keys(password: str, salt: bytes) -> tuple:
    """Derive encryption and HMAC keys using PBKDF2-HMAC-SHA256."""
    key_material = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000,
        dklen=64
    )
    enc_key = key_material[:32]
    mac_key = key_material[32:]
    return enc_key, mac_key

def _generate_keystream(enc_key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate deterministic keystream using counter mode over HMAC-SHA256."""
    keystream = bytearray()
    counter = 0
    while len(keystream) < length:
        block_msg = nonce + counter.to_bytes(4, byteorder='big')
        block = hmac.new(enc_key, block_msg, hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1
    return bytes(keystream[:length])

def _encrypt_payload(data_bytes: bytes, password: str) -> dict:
    """Encrypt payload bytes using PBKDF2 + CTR-HMAC encryption."""
    salt = os.urandom(16)
    nonce = os.urandom(16)
    enc_key, mac_key = _derive_keys(password, salt)
    
    keystream = _generate_keystream(enc_key, nonce, len(data_bytes))
    ciphertext = bytes(a ^ b for a, b in zip(data_bytes, keystream))
    
    # Calculate HMAC over salt + nonce + ciphertext
    mac = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    
    return {
        "salt": base64.b64encode(salt).decode('ascii'),
        "nonce": base64.b64encode(nonce).decode('ascii'),
        "ciphertext": base64.b64encode(ciphertext).decode('ascii'),
        "mac": base64.b64encode(mac).decode('ascii')
    }

def _decrypt_payload(encrypted_dict: dict, password: str) -> bytes:
    """Decrypt payload bytes verifying HMAC tag."""
    try:
        salt = base64.b64decode(encrypted_dict["salt"])
        nonce = base64.b64decode(encrypted_dict["nonce"])
        ciphertext = base64.b64decode(encrypted_dict["ciphertext"])
        expected_mac = base64.b64decode(encrypted_dict["mac"])
    except Exception as e:
        raise InvalidProfileFormatError(f"Invalid base64 payload in encrypted section: {e}")
        
    enc_key, mac_key = _derive_keys(password, salt)
    calculated_mac = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    
    if not hmac.compare_digest(calculated_mac, expected_mac):
        raise InvalidPasswordError("Incorrect password or corrupted profile data.")
        
    keystream = _generate_keystream(enc_key, nonce, len(ciphertext))
    data_bytes = bytes(a ^ b for a, b in zip(ciphertext, keystream))
    return data_bytes

def config_to_dict(config) -> dict:
    """Convert ConfigParser or dict to dictionary representation."""
    if isinstance(config, dict):
        return config
    result = {}
    for section in config.sections():
        result[section] = dict(config[section])
    return result

def dict_to_configparser(data_dict) -> configparser.ConfigParser:
    """Convert dictionary representation to ConfigParser object."""
    config = configparser.ConfigParser()
    for section, options in data_dict.items():
        if isinstance(options, dict):
            config.add_section(section)
            for k, v in options.items():
                config.set(section, k, str(v))
    return config

def export_profile_to_omni(config, profile_name: str, note: str = "", password: str = None, output_path: str = None) -> dict:
    """Export configuration to an .omni profile dictionary / file."""
    config_data = config_to_dict(config)
    
    if not profile_name or not profile_name.strip():
        profile_name = "Untitled_Profile"

    metadata = {
        "omni_format": FORMAT_VERSION,
        "software": SOFTWARE_NAME,
        "profile_name": profile_name.strip(),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": note.strip() if note else "",
        "is_encrypted": bool(password)
    }

    if password:
        raw_json_bytes = json.dumps(config_data, ensure_ascii=False, indent=2).encode('utf-8')
        enc_info = _encrypt_payload(raw_json_bytes, password)
        metadata["encrypted_payload"] = enc_info
    else:
        metadata["config"] = config_data

    if output_path:
        if not (output_path.lower().endswith(".ot") or output_path.lower().endswith(".omni")):
            output_path += ".ot"
        parent_dir = os.path.dirname(os.path.abspath(output_path))
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata

def import_profile_from_omni(input_path_or_str: str, password: str = None) -> tuple:
    """
    Import an .omni profile from file path or JSON string.
    Returns tuple: (config_dict, metadata_dict)
    """
    if os.path.exists(input_path_or_str):
        with open(input_path_or_str, 'r', encoding='utf-8') as f:
            raw_content = f.read()
    else:
        raw_content = input_path_or_str

    try:
        profile_data = json.loads(raw_content)
    except Exception as e:
        raise InvalidProfileFormatError(f"File is not a valid JSON document: {e}")

    if not isinstance(profile_data, dict):
        raise InvalidProfileFormatError("Invalid profile data format (expected JSON object).")

    if profile_data.get("omni_format") != FORMAT_VERSION:
        fmt = profile_data.get("omni_format")
        if fmt is None:
            raise InvalidProfileFormatError("Missing 'omni_format' identifier in profile.")
        raise InvalidProfileFormatError(f"Unsupported profile format version: '{fmt}' (expected '{FORMAT_VERSION}').")

    is_encrypted = profile_data.get("is_encrypted", False)

    if is_encrypted:
        if not password:
            raise InvalidPasswordError("This profile is password protected. Password required.")
        enc_info = profile_data.get("encrypted_payload")
        if not enc_info or not isinstance(enc_info, dict):
            raise InvalidProfileFormatError("Missing encrypted payload in profile.")
        decrypted_bytes = _decrypt_payload(enc_info, password)
        try:
            config_dict = json.loads(decrypted_bytes.decode('utf-8'))
        except Exception as e:
            raise InvalidProfileFormatError(f"Decrypted payload is corrupted: {e}")
    else:
        config_dict = profile_data.get("config")
        if not config_dict or not isinstance(config_dict, dict):
            raise InvalidProfileFormatError("Missing 'config' section in profile.")

    metadata = {
        "omni_format": profile_data.get("omni_format"),
        "software": profile_data.get("software"),
        "profile_name": profile_data.get("profile_name", "Imported_Profile"),
        "created_at": profile_data.get("created_at"),
        "note": profile_data.get("note", ""),
        "is_encrypted": is_encrypted
    }

    return config_dict, metadata

def save_omni_to_ini_file(config_dict: dict, target_ini_path: str):
    """Save an imported config dict directly to an INI settings file."""
    config = dict_to_configparser(config_dict)
    parent_dir = os.path.dirname(os.path.abspath(target_ini_path))
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    with open(target_ini_path, 'w', encoding='utf-8') as f:
        config.write(f)

def main():
    parser = argparse.ArgumentParser(description="OmniTunnel CLI - .ot Profile Manager")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Export sub-command
    export_parser = subparsers.add_parser("export", help="Export an INI configuration to an .ot profile")
    export_parser.add_argument("--input", "-i", required=True, help="Input INI config file path")
    export_parser.add_argument("--output", "-o", required=True, help="Output .ot profile file path")
    export_parser.add_argument("--name", "-n", default="My_Profile", help="Profile name")
    export_parser.add_argument("--note", default="", help="Optional description note")
    export_parser.add_argument("--password", "-p", default=None, help="Optional password to encrypt the profile")

    # Import sub-command
    import_parser = subparsers.add_parser("import", help="Import an .ot / .omni profile to an INI configuration file")
    import_parser.add_argument("--input", "-i", required=True, help="Input .ot / .omni profile file path")
    import_parser.add_argument("--output", "-o", required=True, help="Output INI config file path")
    import_parser.add_argument("--password", "-p", default=None, help="Password for encrypted profiles")

    args = parser.parse_args()

    if args.command == "export":
        if not os.path.exists(args.input):
            print(f"Error: Input INI file '{args.input}' not found.", file=sys.stderr)
            sys.exit(1)
        config = configparser.ConfigParser()
        config.read(args.input)
        try:
            export_profile_to_omni(
                config,
                profile_name=args.name,
                note=args.note,
                password=args.password,
                output_path=args.output
            )
            print(f"✔ Successfully exported profile to '{args.output}'")
        except Exception as e:
            print(f"✕ Export error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "import":
        if not os.path.exists(args.input):
            print(f"Error: Input profile file '{args.input}' not found.", file=sys.stderr)
            sys.exit(1)
        try:
            config_dict, meta = import_profile_from_omni(args.input, password=args.password)
            save_omni_to_ini_file(config_dict, args.output)
            print(f"✔ Successfully imported profile '{meta['profile_name']}' to '{args.output}'")
        except InvalidPasswordError as e:
            print(f"✕ Password error: {e}", file=sys.stderr)
            sys.exit(2)
        except Exception as e:
            print(f"✕ Import error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
