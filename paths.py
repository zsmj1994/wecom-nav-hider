"""Discover the application without changing its installation or configuration."""

import os
from pathlib import Path
import winreg


def executable(value):
    if not value:
        return None
    path = Path(os.path.expandvars(value.strip().strip('"')))
    if path.is_dir():
        path = path / "WXWork.exe"
    if path.name.lower() == "wxwork.exe" and path.is_file():
        return path.resolve()
    return None


def candidates():
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            for key_name, fields in [
                (
                    r"Software\Microsoft\Windows\CurrentVersion\App Paths\WXWork.exe",
                    ("", "Path"),
                ),
                (
                    r"Software\Tencent\WXWork",
                    ("InstallPath", "InstallDir", "InstallLocation"),
                ),
                (
                    r"Software\Microsoft\Windows\CurrentVersion\Uninstall\WXWork",
                    ("InstallLocation", "DisplayIcon"),
                ),
            ]:
                try:
                    with winreg.OpenKey(
                        hive, key_name, 0, winreg.KEY_READ | view
                    ) as key:
                        for field in fields:
                            try:
                                value = winreg.QueryValueEx(key, field)[0]
                                if isinstance(value, str):
                                    yield (
                                        value.rsplit(",", 1)[0]
                                        if field == "DisplayIcon"
                                        else value
                                    )
                            except OSError:
                                pass
                except OSError:
                    pass
    for variable in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        root = os.environ.get(variable)
        if root:
            for suffix in ("WXWork", "Tencent/WXWork", "Programs/WXWork"):
                yield str(Path(root) / suffix / "WXWork.exe")


def find_wecom(configured="", additional=None):
    for value in [configured, *(candidates() if additional is None else additional)]:
        found = executable(value)
        if found:
            return found
    return None


def find_dui(exe, expected_hash):
    import hashlib

    # Derive from the detected installation; never assume a particular version folder.
    found = [exe.parent / "DuiLib.dll", *sorted(exe.parent.glob("*/DuiLib.dll"))]
    for candidate in found:
        if (
            candidate.is_file()
            and hashlib.sha256(candidate.read_bytes()).hexdigest() == expected_hash
        ):
            return candidate
    raise RuntimeError(
        "未找到匹配的 DuiLib 界面库。路径检测不能替代版本兼容，需要重新定位。"
    )
