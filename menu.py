#!/usr/bin/env python3
import sys
from src.menu_common import C_RED, C_RESET
from src.menu_options import menu_main


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = 'number' if '--number' in argv else 'arrows'
    try:
        menu_main(mode=mode)
    except KeyboardInterrupt:
        print()
    except Exception as e:
        print(f"{C_RED}Error: {e}{C_RESET}")
        sys.exit(1)


if __name__ == '__main__':
    main()
