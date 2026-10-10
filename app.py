"""Portable executable entry point; default action opens the terminal picker."""

import argparse
import ctypes
import json
import sys

from runtime import app_root, ensure_config, frozen, start_child


def main():
    parser = argparse.ArgumentParser(description="WeCom Nav Hider")
    modes = parser.add_mutually_exclusive_group()
    for mode in ("start", "background", "stop", "check", "self-test"):
        modes.add_argument("--" + mode, action="store_true")
    args = parser.parse_args()
    if args.self_test:
        import frida
        import launcher
        from tui import Selection
        assert "__BUILD_CONFIG__" in launcher.JS
        assert launcher.BUILD["architecture"] == "ia32"
        assert "智能助理" in Selection(["智能助理"]).render()
        # Exercise the bundled native extension without attaching to any process.
        frida.get_local_device().enumerate_processes()
        print(json.dumps({"frozen": frozen(), "frida": frida.__version__, "ok": True}))
        return
    if args.stop:
        from launcher import request_stop
        request_stop()
        return
    ensure_config(app_root())
    if args.start:
        start_child(True)
    elif args.background or args.check:
        from launcher import run
        run()
    else:
        from tui import main as choose
        choose()


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print(f"启动失败：{error}", file=sys.stderr)
        if not any(arg in sys.argv for arg in ("--check", "--self-test", "--background")):
            ctypes.windll.user32.MessageBoxW(None, str(error), "WeCom Nav Hider", 0x10)
        sys.exit(1)
