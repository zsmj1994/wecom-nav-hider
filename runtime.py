"""Resource and process paths shared by source and portable builds."""

import os
from pathlib import Path
import subprocess
import sys

RESOURCE_ROOT = Path(__file__).resolve().parent


def frozen():
    return getattr(sys, "frozen", False)


def app_root():
    return Path(sys.executable).parent if frozen() else RESOURCE_ROOT


def ensure_config(root):
    sample = (RESOURCE_ROOT / "config.example.json").read_bytes()
    try:
        with (root / "config.json").open("xb") as output:
            output.write(sample)
    except FileExistsError:
        pass


def saved_paths(previous, wecom):
    result = dict(previous, wecom=str(wecom))
    if frozen():
        result.pop("python", None)
    else:
        result["python"] = str(Path(sys.executable).with_name("python.exe"))
    return result


def child_command(background):
    if frozen():
        return [sys.executable, *(["--background"] if background else [])]
    python = Path(sys.executable).with_name("pythonw.exe" if background else "python.exe")
    return [str(python), str(RESOURCE_ROOT / ("launcher.py" if background else "tui.py")),
            *(["--background"] if background else [])]


def start_child(background):
    return subprocess.Popen(
        child_command(background),
        cwd=app_root(),
        env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"),
        creationflags=subprocess.CREATE_NO_WINDOW if background else subprocess.CREATE_NEW_CONSOLE,
        stdin=subprocess.DEVNULL if background else None,
        stdout=subprocess.DEVNULL if background else None,
        stderr=subprocess.DEVNULL if background else None,
    )
