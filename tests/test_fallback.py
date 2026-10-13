import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import launcher


class FallbackTests(unittest.TestCase):
    def test_unsupported_starts_normally_without_loading_frida(self):
        self.assertTrue(
            hasattr(launcher, "launch_normal"), "normal launch fallback missing"
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe = root / "WXWork.exe"
            exe.touch()
            (root / "config.json").write_text(
                json.dumps({"hide": []}), encoding="utf-8"
            )
            with (
                patch.object(launcher, "ROOT", root),
                patch.object(launcher, "find_wecom", return_value=exe),
                patch.object(
                    launcher, "resolve", return_value=(None, None, "no matching build")
                ),
                patch("sys.argv", ["launcher.py"]),
                patch("subprocess.Popen") as spawn,
                patch.dict("sys.modules", {"frida": None}),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                launcher.main()
            self.assertEqual(spawn.call_args.args[0], [str(exe)])
            self.assertIn("未启用导航隐藏", output.getvalue())

    def test_check_never_starts_unsupported_client(self):
        self.assertTrue(
            hasattr(launcher, "launch_normal"), "normal launch fallback missing"
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "config.json").write_text('{"hide":[]}', encoding="utf-8")
            with (
                patch.object(launcher, "ROOT", root),
                patch.object(launcher, "find_wecom", return_value=root / "WXWork.exe"),
                patch.object(
                    launcher, "resolve", return_value=(None, None, "no match")
                ),
                patch("sys.argv", ["launcher.py", "--check"]),
                patch("subprocess.Popen") as spawn,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                launcher.main()
            spawn.assert_not_called()
            self.assertIn("未启动", output.getvalue())


if __name__ == "__main__":
    unittest.main()
