import argparse
import ctypes
import hashlib
import json
import sys
import threading
from pathlib import Path
from settings import ConfigWatcher, write_config
from paths import find_wecom, find_dui
from runtime import RESOURCE_ROOT, app_root, saved_paths, start_child

ROOT = app_root()
sys.path.insert(0, str(ROOT / "deps"))
BUILD = json.loads((RESOURCE_ROOT / "compatibility.json").read_text(encoding="utf-8"))
EXPECTED = BUILD["exe_sha256"]
DUI_EXPECTED = BUILD["dui_sha256"]
JS = (RESOURCE_ROOT / "hooks" / "navigation.js").read_text(encoding="utf-8")


STOP_EVENT = "Local\\WeComNavigationLauncher_Stop_20261010"


def event_api():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateEventW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_wchar_p,
    ]
    kernel.CreateEventW.restype = ctypes.c_void_p
    kernel.OpenEventW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    kernel.OpenEventW.restype = ctypes.c_void_p
    kernel.SetEvent.argtypes = [ctypes.c_void_p]
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    return kernel


def request_stop():
    kernel = event_api()
    handle = kernel.OpenEventW(2, False, STOP_EVENT)
    if not handle:
        if ctypes.get_last_error() == 2:
            print("启动器未运行。")
            return
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not kernel.SetEvent(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        print("已请求撤销；刷新导航或重启企业微信可恢复入口。")
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if args.stop:
        request_stop()
        return
    config = ConfigWatcher(ROOT / "config.json")
    EXE = find_wecom(config.current["paths"].get("wecom", ""))
    if EXE is None:
        if args.background:
            start_child(False)
            print("未检测到企业微信，已打开终端填写路径。", flush=True)
            return
        raise RuntimeError(
            "未检测到企业微信。请双击 Start-WeCom.cmd，在终端中填写 WXWork.exe 路径。"
        )
    if hashlib.sha256(EXE.read_bytes()).hexdigest() != EXPECTED:
        raise RuntimeError(
            "企业微信版本已变化。为避免使用错误地址，已停止；需要重新定位后更新启动器。"
        )
    DUI = find_dui(EXE, DUI_EXPECTED)
    try:
        import frida
    except ImportError as error:
        raise RuntimeError("未安装 Frida。请先运行 Setup.cmd 安装依赖。") from error
    if args.check:
        print(
            f"校验通过：企业微信文件、Python、Frida {frida.__version__}、config.json。未启动或挂载进程。"
        )
        print("配置隐藏：" + ("、".join(config.current["items"]) or "无"))
        print(f"企业微信：{EXE}\n界面库：{DUI}\nPython：{sys.executable}")
        return
    resolved_paths = saved_paths(config.current["paths"], EXE)
    if resolved_paths != config.current["paths"]:
        write_config(ROOT / "config.json", config.current["items"], resolved_paths)
        config = ConfigWatcher(ROOT / "config.json")
    kernel = event_api()
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = kernel.CreateMutexW(None, False, "Local\\WeComNavigationLauncher_20261010")
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(mutex)
        raise RuntimeError("启动器已经在运行，请使用原来的窗口。")
    session = script = None
    spawned = resumed = False
    pid = None
    stop_event = None
    try:
        stop_event = kernel.CreateEventW(None, True, False, STOP_EVENT)
        if not stop_event:
            raise ctypes.WinError(ctypes.get_last_error())
        device = frida.get_local_device()
        candidates = [
            p for p in device.enumerate_processes() if p.name.lower() == "wxwork.exe"
        ]
        if len(candidates) > 1:
            raise RuntimeError(
                "发现多个 WXWork.exe，未自动选择。请退出企业微信后重新运行启动器。"
            )
        if candidates:
            pid = candidates[0].pid
            # Verify the existing process image belongs to this installation.
            kernel.OpenProcess.argtypes = [
                ctypes.c_uint32,
                ctypes.c_int,
                ctypes.c_uint32,
            ]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.QueryFullProcessImageNameW.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_wchar_p,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            handle = kernel.OpenProcess(0x1000, False, pid)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                path = ctypes.create_unicode_buffer(32768)
                size = ctypes.c_uint32(len(path))
                if not kernel.QueryFullProcessImageNameW(
                    handle, 0, path, ctypes.byref(size)
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
                if Path(path.value).resolve() != EXE.resolve():
                    raise RuntimeError("运行中的企业微信路径不匹配，停止挂载。")
            finally:
                kernel.CloseHandle(handle)
        else:
            pid = device.spawn([str(EXE)], cwd=str(EXE.parent))
            spawned = True
        session = device.attach(pid)
        done = threading.Event()
        session.on("detached", lambda *args: done.set())
        source = JS.replace(
            "__INITIAL_CONFIG__", json.dumps(config.current, ensure_ascii=True)
        )
        source = source.replace(
            "__BUILD_CONFIG__", json.dumps(BUILD, ensure_ascii=True)
        )
        script = session.create_script(source)

        def message(msg, data):
            if msg["type"] == "send":
                print(msg["payload"], flush=True)
            elif msg["type"] == "error":
                print("探针错误：" + msg.get("description", str(msg)), flush=True)
                done.set()

        script.on("message", message)
        script.load()
        if spawned:
            device.resume(pid)
            resumed = True
        print("已挂载。若入口仍显示，切换通讯录再返回消息。", flush=True)
        print("配置隐藏：" + ("、".join(config.current["items"]) or "无"), flush=True)
        print("修改 config.json 会自动加载，在导航下次刷新时生效。", flush=True)
        print("运行 Stop-Hiding.vbs 撤销；企业微信退出后启动器自动结束。", flush=True)
        try:
            while not done.wait(1):
                if kernel.WaitForSingleObject(stop_event, 0) == 0:
                    break
                config.poll(
                    script.exports_sync.configure, lambda text: print(text, flush=True)
                )
        except KeyboardInterrupt:
            print("\n正在撤销……", flush=True)
    finally:
        try:
            if session and not session.is_detached:
                try:
                    if script:
                        script.exports_sync.stop()
                finally:
                    session.detach()
        finally:
            try:
                if spawned and not resumed:
                    device.resume(pid)
            finally:
                if stop_event:
                    kernel.CloseHandle(stop_event)
                kernel.CloseHandle(mutex)
    print("已结束。恢复入口可刷新导航或重启企业微信。")


def run():
    background = "--background" in sys.argv
    if background:
        sys.stdout = sys.stderr = (ROOT / "launcher.log").open(
            "a", encoding="utf-8", buffering=1
        )
    try:
        main()
    except Exception as error:
        print(f"启动失败：{error}", file=sys.stderr)
        if background:
            ctypes.windll.user32.MessageBoxW(
                None, str(error), "企业微信导航启动器", 0x10
            )
        sys.exit(1)


if __name__ == "__main__":
    run()
