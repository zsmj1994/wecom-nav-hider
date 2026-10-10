"""Windows terminal picker; saves preferences and starts the windowless helper."""

import ctypes
import sys

from settings import NAV_ITEMS, parse_config, write_config
from paths import find_wecom, executable
from runtime import app_root, saved_paths, start_child

ROOT = app_root()
MUTEX = "Local\\WeComNavigationLauncher_20261010"


class Selection:
    def __init__(self, selected):
        self.names = list(NAV_ITEMS)
        self.selected = set(selected)
        self.cursor = 0

    def key(self, key):
        if key == "up":
            self.cursor = (self.cursor - 1) % len(self.names)
        elif key == "down":
            self.cursor = (self.cursor + 1) % len(self.names)
        elif key == " ":
            item = self.names[self.cursor]
            self.selected.symmetric_difference_update([item])
        elif key.lower() == "a":
            self.selected = set(self.names)
        elif key.lower() == "n":
            self.selected.clear()
        elif key == "enter":
            return "save"
        elif key in ("escape", "\x03") or key.lower() == "q":
            return "cancel"

    def items(self):
        return [name for name in self.names if name in self.selected]

    def render(self):
        lines = [
            "企业微信 · 导航隐藏设置",
            "",
            "勾选 = 隐藏；未勾选 = 交由企业微信正常显示。",
            "↑/↓ 移动  空格 勾选  A 全选  N 清空",
            "Enter 保存并后台运行  Esc/Q 取消",
            "",
        ]
        for index, name in enumerate(self.names):
            marker = ">" if index == self.cursor else " "
            check = "x" if name in self.selected else " "
            lines.append(f" {marker} [{check}] {name}")
        lines += [
            "",
            f"已选 {len(self.selected)} 项；消息入口始终保留。",
            "保存后可关闭窗口；界面变化需等导航刷新。",
        ]
        return "\n".join(lines)


def save_config(path, items):
    paths = parse_config(path.read_bytes())["paths"] if path.exists() else {}
    write_config(path, items, paths)


def background_running():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenMutexW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    kernel.OpenMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenMutexW(0x100000, False, MUTEX)
    if handle:
        kernel.CloseHandle(handle)
        return True
    if ctypes.get_last_error() != 2:
        raise ctypes.WinError(ctypes.get_last_error())
    return False


def choose(selection):
    import msvcrt

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("请双击 Start-WeCom.cmd，在交互终端中打开选择界面。")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.argtypes = [ctypes.c_uint32]
    kernel.GetStdHandle.restype = ctypes.c_void_p
    kernel.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    handle = kernel.GetStdHandle(0xFFFFFFF5)
    old_mode = ctypes.c_uint32()
    if not kernel.GetConsoleMode(handle, ctypes.byref(old_mode)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not kernel.SetConsoleMode(handle, old_mode.value | 4):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        print("\x1b[?1049h\x1b[?25l", end="", flush=True)
        while True:
            print("\x1b[H\x1b[2J" + selection.render(), end="", flush=True)
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                key = {"H": "up", "P": "down"}.get(msvcrt.getwch(), "ignored")
            else:
                key = {"\r": "enter", "\x1b": "escape"}.get(key, key)
            action = selection.key(key)
            if action:
                return action
    finally:
        print("\x1b[?25h\x1b[?1049l", end="", flush=True)
        kernel.SetConsoleMode(handle, old_mode.value)


def main():
    config_path = ROOT / "config.json"
    config = parse_config(config_path.read_bytes())
    wecom = find_wecom(config["paths"].get("wecom", ""))
    while wecom is None:
        print("未检测到企业微信。输入 WXWork.exe 完整路径或安装目录；留空取消。")
        value = input("企业微信路径：").strip()
        if not value:
            print("已取消，配置未修改。")
            return
        wecom = executable(value)
        if wecom is None:
            print("该位置没有 WXWork.exe，请重新填写。")
    print(f"企业微信：{wecom}")
    selection = Selection(config["items"])
    if choose(selection) == "cancel":
        print("已取消，配置未修改。")
        return
    write_config(
        config_path,
        selection.items(),
        saved_paths(config["paths"], wecom),
    )
    if background_running():
        print("已保存。现有后台启动器将自动加载新选择。")
    else:
        start_child(True)
        print("已保存并启动后台程序；挂载失败会弹窗提示。")
    print("隐藏名单：" + ("、".join(selection.items()) or "无"))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
    except Exception as error:
        print(f"操作失败：{error}", file=sys.stderr)
        sys.exit(1)
