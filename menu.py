#!/usr/bin/env python3
import sys
import subprocess
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    if argv and argv[0] == 'run':
        sys.path.insert(0, BASE_DIR)
        from src.menu_common import load_profile

        args = argv[1:]
        proxy_flag = '--proxy' in args
        if proxy_flag:
            args.remove('--proxy')

        if args:
            if not load_profile(args[0]):
                sys.exit(1)

        script = os.path.join(BASE_DIR, 'runvpn.sh')
        cmd = ['bash', script]
        if proxy_flag:
            cmd.append('--proxy')
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            pass
        return

    from src.menu_common import C_RED, C_RESET
    from src.menu_options import menu_main
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
