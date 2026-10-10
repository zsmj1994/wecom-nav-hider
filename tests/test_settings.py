import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from settings import ConfigWatcher, parse_config


def raw(names):
    return json.dumps({"hide": names}, ensure_ascii=False).encode("utf-8")


class SettingsTests(unittest.TestCase):
    def test_empty_and_bom(self):
        self.assertEqual(
            parse_config(b"\xef\xbb\xbf" + raw([])),
            {"assistant": False, "controls": [], "items": [], "paths": {}},
        )

    def test_document_categories_are_independent(self):
        smart = parse_config(raw(["智能文档"]))
        ordinary = parse_config(raw(["文档"]))
        self.assertIn("smart_sheet_op_layout", smart["controls"])
        self.assertFalse(set(smart["controls"]) & set(ordinary["controls"]))
        self.assertFalse(smart["assistant"])
        self.assertTrue(parse_config(raw(["智能助理"]))["assistant"])

    def test_reject_invalid_input(self):
        for invalid in [
            b"{}",
            b'{"hide":true}',
            b'{"hide":[false]}',
            raw(["消息"]),
            raw(["微盘", "微盘"]),
            b'{"hide":[],"typo":1}',
            b'{"hide":[],"hide":[]}',
            b"{",
        ]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_config(invalid)

    def test_live_edits_keep_last_good_then_recover(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_bytes(raw(["微盘"]))
            watcher = ConfigWatcher(path)
            applied, logs = [], []
            watcher.poll(applied.append, logs.append)
            self.assertFalse(applied)
            path.write_bytes(b"{")
            watcher.poll(applied.append, logs.append)
            watcher.poll(applied.append, logs.append)
            self.assertEqual(len(logs), 1)
            self.assertEqual(watcher.current["items"], ["微盘"])
            self.assertFalse(applied)
            path.unlink()
            watcher.poll(applied.append, logs.append)
            self.assertEqual(watcher.current["items"], ["微盘"])
            path.write_bytes(raw([]))
            watcher.poll(applied.append, logs.append)
            self.assertEqual(applied[-1]["controls"], [])
            self.assertEqual(watcher.current["items"], [])

    def test_failed_rpc_keeps_active_snapshot_and_retries(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_bytes(raw(["微盘"]))
            watcher = ConfigWatcher(path)
            path.write_bytes(raw(["智能助理"]))

            def fail(_):
                raise RuntimeError("RPC failed")

            watcher.poll(fail, lambda _: None)
            self.assertEqual(watcher.current["items"], ["微盘"])
            applied = []
            watcher.poll(applied.append, lambda _: None)
            self.assertTrue(applied[0]["assistant"])


if __name__ == "__main__":
    unittest.main()
