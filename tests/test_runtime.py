import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class RuntimeTests(unittest.TestCase):
    def runtime(self):
        self.assertIsNotNone(importlib.util.find_spec("runtime"), "packaged runtime missing")
        import runtime
        return runtime

    def test_frozen_child_uses_exe_without_python(self):
        runtime = self.runtime()
        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "executable", "C:/portable/WeComNavHider.exe"
        ):
            self.assertEqual(runtime.app_root(), Path(sys.executable).parent)
            self.assertEqual(runtime.child_command(True), [sys.executable, "--background"])
            self.assertEqual(runtime.child_command(False), [sys.executable])
            self.assertNotIn("python", runtime.saved_paths({}, Path("WXWork.exe")))

    def test_source_child_keeps_pythonw(self):
        runtime = self.runtime()
        with patch.object(sys, "frozen", False, create=True):
            command = runtime.child_command(True)
            self.assertEqual(Path(command[0]).name, "pythonw.exe")
            self.assertEqual(Path(command[1]).name, "launcher.py")

    def test_first_run_does_not_overwrite_preferences(self):
        runtime = self.runtime()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            runtime.ensure_config(root)
            self.assertTrue((root / "config.json").exists())
            original = b'{"hide":[]}'
            (root / "config.json").write_bytes(original)
            runtime.ensure_config(root)
            self.assertEqual((root / "config.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
