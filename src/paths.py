import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVED_CONFIGS_DIR = os.path.join(PROJECT_DIR, "cfgs", "saved")
CONFIG_PATH = os.path.join(SAVED_CONFIGS_DIR, "active.ot")  # unified active .ot
CONFIG_EXAMPLE_PATH = os.path.join(PROJECT_DIR, "cfgs", "settings.ot.example")
LOGS_DIR = os.path.join(PROJECT_DIR, "logs")
SESSION_LOG_PATH = os.path.join(LOGS_DIR, "session.log")
SINGBOX_BIN_LOCAL = os.path.join(PROJECT_DIR, "bin", "sing-box")

# Alias for legacy code
BASE_DIR = PROJECT_DIR
