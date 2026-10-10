import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
import tui
from settings import parse_config, write_config


class PathTests(unittest.TestCase):
    def test_configured_priority_and_stale_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            a = root / "安装 路径 A"
            a.mkdir()
            (a / "WXWork.exe").touch()
            b = root / "B"
            b.mkdir()
            (b / "WXWork.exe").touch()
            self.assertEqual(paths.find_wecom(str(a), [str(b)]), a / "WXWork.exe")
            self.assertEqual(
                paths.find_wecom(str(root / "missing"), [str(b)]), b / "WXWork.exe"
            )
            self.assertIsNone(paths.find_wecom("", []))
            self.assertEqual(
                paths.executable('"' + str(a / "WXWork.exe") + '"'), a / "WXWork.exe"
            )

    def test_legacy_config_and_preserve_paths_on_hide_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "config.json"
            p.write_text('{"hide":[]}', encoding="utf-8")
            self.assertEqual(parse_config(p.read_bytes())["paths"], {})
            expected = {"wecom": "D:/应用/WXWork.exe", "python": "D:/Python/python.exe"}
            write_config(p, ["微盘"], expected)
            tui.save_config(p, ["智能助理"])
            self.assertEqual(parse_config(p.read_bytes())["paths"], expected)

    def test_bad_paths_rejected(self):
        for obj in [[], {"wecom": 1}, {"typo": "x"}]:
            with self.subTest(obj=obj), self.assertRaises(ValueError):
                parse_config(json.dumps({"hide": [], "paths": obj}).encode())

    def test_manual_fallback_saved_only_on_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe = root / "WXWork.exe"
            exe.touch()
            cfg = root / "config.json"
            write_config(cfg, ["微盘"], {})
            with (
                patch.object(tui, "ROOT", root),
                patch.object(tui, "find_wecom", return_value=None),
                patch("builtins.input", side_effect=["not-exist", str(exe)]),
                patch.object(tui, "choose", return_value="save"),
                patch.object(tui, "background_running", return_value=True),
            ):
                tui.main()
            saved = parse_config(cfg.read_bytes())
            self.assertEqual(saved["paths"]["wecom"], str(exe))
            self.assertEqual(saved["items"], ["微盘"])
            before = cfg.read_bytes()
            with (
                patch.object(tui, "ROOT", root),
                patch.object(tui, "find_wecom", return_value=None),
                patch("builtins.input", return_value=""),
            ):
                tui.main()
            self.assertEqual(cfg.read_bytes(), before)

    def test_dui_hash_guard(self):
        import hashlib

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sub = root / "different-version-folder"
            sub.mkdir()
            dll = sub / "DuiLib.dll"
            dll.write_bytes(b"expected")
            self.assertEqual(
                paths.find_dui(
                    root / "WXWork.exe", hashlib.sha256(b"expected").hexdigest()
                ),
                dll,
            )
            with self.assertRaises(RuntimeError):
                paths.find_dui(root / "WXWork.exe", "wrong")


if __name__ == "__main__":
    unittest.main()
