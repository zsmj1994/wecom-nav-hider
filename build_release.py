"""Build a Windows x64 portable ZIP in an isolated Python environment."""

import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
NAME = "WeComNavHider"
VERSION = "0.1.0"


def main():
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise RuntimeError("Build with 64-bit Python on Windows x64")
    output = ROOT / "dist" / NAME
    if output.exists():
        raise RuntimeError("dist/WeComNavHider already exists; use a fresh build directory")
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--console",
        "--name", NAME, "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
        "--collect-all", "frida", "--add-data", str(ROOT / "compatibility.json") + ";.",
        "--add-data", str(ROOT / "config.example.json") + ";.",
        "--add-data", str(ROOT / "hooks/navigation.js") + ";hooks",
        "app.py",
    ], cwd=ROOT, check=True)
    for name in ("README.md", "LICENSE", "config.example.json"):
        shutil.copy2(ROOT / name, output / name)
    shutil.copytree(ROOT / "docs", output / "docs")
    notices = output / "licenses"
    notices.mkdir()
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", notices / "Python-LICENSE.txt")
    for package in ("frida", "pyinstaller"):
        distribution = importlib.metadata.distribution(package)
        for item in distribution.files or []:
            if any(word in item.name.lower() for word in ("license", "copying")):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    shutil.copy2(source, notices / (package + "-" + item.name))
    (output / "Stop-Hiding.cmd").write_text(
        '@echo off\n"%~dp0WeComNavHider.exe" --stop\npause\n', encoding="ascii"
    )
    (output / "Start-Background.vbs").write_text(
        'Set shell = CreateObject("WScript.Shell")\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        'exe = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "WeComNavHider.exe")\n'
        'shell.Run Chr(34) & exe & Chr(34) & " --start", 0, False\n', encoding="ascii"
    )
    (output / "BUILD.json").write_text(json.dumps({
        "version": VERSION, "platform": "windows-x64", "python": platform.python_version(),
        "frida": importlib.metadata.version("frida"),
        "pyinstaller": importlib.metadata.version("pyinstaller"),
    }, indent=2) + "\n", encoding="utf-8")
    subprocess.run([str(output / (NAME + ".exe")), "--self-test"], check=True)
    archive = ROOT / "dist" / f"wecom-nav-hider-v{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(output.parent))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (ROOT / "dist" / "SHA256SUMS.txt").write_text(
        f"{checksum}  {archive.name}\n", encoding="ascii"
    )
    print(archive)


if __name__ == "__main__":
    main()
