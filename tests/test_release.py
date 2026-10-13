import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from settings import parse_config
from tui import Selection, save_config


class ReleaseTests(unittest.TestCase):
    def test_sample_contains_no_machine_paths(self):
        sample = parse_config((ROOT / "config.example.json").read_bytes())
        self.assertEqual(sample["paths"], {"wecom": "", "python": ""})
        self.assertEqual(sample["items"], ["智能助理"])

    def test_adaptation_constants_match_verified_call_sites(self):
        build = json.loads((ROOT / "compatibility.json").read_text(encoding="utf-8"))
        self.assertEqual(build["version"], "5.0.12.6013")
        self.assertEqual(build["assistant_predicate_rva"], 0x256A700)
        self.assertEqual(build["navigation_return_rva"], 0x6CE5C54)
        self.assertEqual(build["architecture"], "ia32")
        for key in ["exe_sha256", "dui_sha256"]:
            self.assertEqual(len(bytes.fromhex(build[key])), 32)

    def test_hook_placeholders_and_navigation_scope(self):
        source = (ROOT / "hooks/navigation.js").read_text(encoding="utf-8")
        self.assertEqual(source.count("__INITIAL_CONFIG__"), 1)
        self.assertEqual(source.count("__BUILD_CONFIG__"), 1)
        self.assertIn("inNavigation", source)
        self.assertIn("settings.assistant", source)

    def test_picker_and_atomic_save(self):
        selection = Selection(["微盘"])
        selection.key(" ")
        self.assertIn("智能助理", selection.items())
        selection.key("up")
        self.assertEqual(selection.names[selection.cursor], "高级功能")
        selection.key("n")
        self.assertEqual(selection.items(), [])
        selection.key("a")
        self.assertEqual(len(selection.items()), 12)
        self.assertEqual(selection.key("escape"), "cancel")
        self.assertEqual(selection.key("enter"), "save")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            save_config(path, ["微盘"])
            self.assertEqual(parse_config(path.read_bytes())["items"], ["微盘"])
            self.assertEqual([p.name for p in Path(folder).iterdir()], ["config.json"])


if __name__ == "__main__":
    unittest.main()
