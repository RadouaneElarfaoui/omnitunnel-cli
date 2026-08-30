#!/usr/bin/env python3
import os
import sys
import unittest
import tempfile
import shutil

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.logger import (
    strip_ansi,
    log_info,
    log_ssh,
    log_singbox,
    log_tunnel,
    log_session_start,
    SESSION_LOG_PATH
)

class TestLogger(unittest.TestCase):
    def test_strip_ansi(self):
        colored_str = "\033[32mConnected\033[0m to \033[1;33mServer\033[0m"
        clean_str = strip_ansi(colored_str)
        self.assertEqual(clean_str, "Connected to Server")

    def test_logging_to_file(self):
        log_session_start()
        log_ssh("\033[32mTest SSH Event\033[0m", print_console=False)
        log_singbox("Test Singbox Event", print_console=False)
        log_tunnel("Test Tunnel Event", print_console=False)

        self.assertTrue(os.path.exists(SESSION_LOG_PATH))
        with open(SESSION_LOG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()

        self.assertIn("OMNITUNNEL SESSION START", content)
        self.assertIn("[SSH] Test SSH Event", content)
        self.assertIn("[SINGBOX] Test Singbox Event", content)
        self.assertIn("[TUNNEL] Test Tunnel Event", content)
        # Ensure ANSI colors were stripped from the file content
        self.assertNotIn("\033[32m", content)

if __name__ == "__main__":
    unittest.main()
