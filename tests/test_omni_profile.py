#!/usr/bin/env python3
import os
import sys
import unittest
import tempfile
import configparser
import shutil

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.omni_profile import (
    export_profile_to_omni,
    import_profile_from_omni,
    save_omni_to_ini_file,
    InvalidPasswordError,
    InvalidProfileFormatError,
    dict_to_configparser,
    config_to_dict
)

class TestOmniProfile(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sample_config = {
            "mode": {
                "connection_mode": "3",
                "auto_replace": "y"
            },
            "ssh": {
                "host": "vps.example.com",
                "port": "443",
                "username": "testuser",
                "password": "secretpassword123",
                "enable_compression": "n",
                "auth_method": "password"
            },
            "Payload": {
                "payload": "GET / HTTP/1.1[crlf]Host: [host][crlf]",
                "proxyip": "proxy.example.com",
                "proxyport": "8080"
            },
            "sni": {
                "server_name": "sni.example.com"
            }
        }

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_unencrypted_export_import_ot(self):
        out_path = os.path.join(self.test_dir, "test_profile.ot")
        export_profile_to_omni(
            self.sample_config,
            profile_name="TestProfile",
            note="Test note description",
            password=None,
            output_path=out_path
        )
        self.assertTrue(os.path.exists(out_path))

        imported_config, metadata = import_profile_from_omni(out_path)
        self.assertEqual(metadata["profile_name"], "TestProfile")
        self.assertEqual(metadata["note"], "Test note description")
        self.assertFalse(metadata["is_encrypted"])
        self.assertEqual(imported_config["ssh"]["host"], "vps.example.com")
        self.assertEqual(imported_config["Payload"]["proxyip"], "proxy.example.com")

    def test_legacy_omni_import_compatibility(self):
        legacy_path = os.path.join(self.test_dir, "legacy_profile.omni")
        export_profile_to_omni(
            self.sample_config,
            profile_name="LegacyOmniProfile",
            password=None,
            output_path=legacy_path
        )
        self.assertTrue(os.path.exists(legacy_path))

        imported_config, metadata = import_profile_from_omni(legacy_path)
        self.assertEqual(metadata["profile_name"], "LegacyOmniProfile")
        self.assertEqual(imported_config["ssh"]["host"], "vps.example.com")

    def test_encrypted_export_import_success(self):
        out_path = os.path.join(self.test_dir, "test_encrypted.ot")
        password = "mySecretPassword!123"
        export_profile_to_omni(
            self.sample_config,
            profile_name="EncryptedProfile",
            note="Encrypted test profile",
            password=password,
            output_path=out_path
        )

        imported_config, metadata = import_profile_from_omni(out_path, password=password)
        self.assertEqual(metadata["profile_name"], "EncryptedProfile")
        self.assertTrue(metadata["is_encrypted"])
        self.assertEqual(imported_config["ssh"]["password"], "secretpassword123")

    def test_encrypted_export_import_wrong_password(self):
        out_path = os.path.join(self.test_dir, "test_encrypted.ot")
        password = "mySecretPassword!123"
        export_profile_to_omni(
            self.sample_config,
            profile_name="EncryptedProfile",
            password=password,
            output_path=out_path
        )

        with self.assertRaises(InvalidPasswordError):
            import_profile_from_omni(out_path, password="WrongPassword")

    def test_encrypted_export_import_missing_password(self):
        out_path = os.path.join(self.test_dir, "test_encrypted.ot")
        password = "mySecretPassword!123"
        export_profile_to_omni(
            self.sample_config,
            profile_name="EncryptedProfile",
            password=password,
            output_path=out_path
        )

        with self.assertRaises(InvalidPasswordError):
            import_profile_from_omni(out_path, password=None)

    def test_invalid_json_format(self):
        out_path = os.path.join(self.test_dir, "corrupt.ot")
        with open(out_path, 'w') as f:
            f.write("{ invalid json content ...")

        with self.assertRaises(InvalidProfileFormatError):
            import_profile_from_omni(out_path)

    def test_ini_file_save_and_roundtrip(self):
        out_ot_path = os.path.join(self.test_dir, "roundtrip.ot")
        out_ini_path = os.path.join(self.test_dir, "settings.ini")

        export_profile_to_omni(
            self.sample_config,
            profile_name="RoundtripProfile",
            output_path=out_ot_path
        )

        imported_dict, _ = import_profile_from_omni(out_ot_path)
        save_omni_to_ini_file(imported_dict, out_ini_path)

        self.assertTrue(os.path.exists(out_ini_path))
        parser = configparser.ConfigParser()
        parser.read(out_ini_path)
        self.assertEqual(parser.get("ssh", "host"), "vps.example.com")
        self.assertEqual(parser.get("sni", "server_name"), "sni.example.com")

if __name__ == "__main__":
    unittest.main()
