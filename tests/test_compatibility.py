import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class CompatibilityTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(
            importlib.util.find_spec("compatibility"), "resolver missing"
        )
        import compatibility

        return compatibility

    def fixture(self, root):
        exe = root / "WXWork.exe"
        # Minimal PE header sufficient for checking machine and image size.
        data = bytearray(512)
        data[:2] = b"MZ"
        data[60:64] = (128).to_bytes(4, "little")
        data[128:132] = b"PE\0\0"
        data[132:134] = (0x14C).to_bytes(2, "little")
        data[152:154] = (0x10B).to_bytes(2, "little")
        data[208:212] = (0x10000000).to_bytes(4, "little")
        exe.write_bytes(data)
        dll = root / "DuiLib.dll"
        dll.write_bytes(b"known dll")
        profile = json.loads((ROOT / "compatibility.json").read_text(encoding="utf-8"))
        profile["exe_sha256"] = hashlib.sha256(data).hexdigest()
        profile["dui_sha256"] = hashlib.sha256(dll.read_bytes()).hexdigest()
        return exe, profile

    def catalog(self, profile):
        return json.dumps(
            {
                "schema_version": 1,
                "hook_api": 1,
                "profiles": [dict(profile, verified=True)],
            }
        ).encode()

    def test_download_match_is_cached_and_works_offline(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe, profile = self.fixture(root)
            cache = root / "cache.json"
            with patch.object(mod, "fetch_catalog", return_value=self.catalog(profile)):
                result = mod.resolve(exe, cache, None)
            self.assertEqual(result[0], profile)
            self.assertTrue(cache.exists())
            with patch.object(mod, "fetch_catalog", side_effect=OSError("offline")):
                result = mod.resolve(exe, cache, None)
            self.assertEqual(result[0], profile)

    def test_unknown_or_wrong_dll_never_matches(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe, profile = self.fixture(root)
            (root / "DuiLib.dll").write_bytes(b"changed")
            with patch.object(mod, "fetch_catalog", return_value=self.catalog(profile)):
                self.assertIsNone(mod.resolve(exe, root / "cache.json", profile)[0])
            exe.write_bytes(b"unknown exe")
            with patch.object(mod, "fetch_catalog", return_value=self.catalog(profile)):
                self.assertIsNone(mod.resolve(exe, root / "cache.json", profile)[0])

    def test_invalid_remote_does_not_replace_valid_cache(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe, profile = self.fixture(root)
            cache = root / "cache.json"
            raw = self.catalog(profile)
            cache.write_bytes(raw)
            with patch.object(mod, "fetch_catalog", return_value=b"{broken"):
                self.assertEqual(mod.resolve(exe, cache, None)[0], profile)
            self.assertEqual(cache.read_bytes(), raw)

    def test_rejects_unverified_script_and_bad_offsets(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as folder:
            _, profile = self.fixture(Path(folder))
            for edits in (
                {"verified": False},
                {"script": "evil()"},
                {"assistant_predicate_rva": True},
                {"control_name_offset": -1},
                {"navigation_container": "unrelated"},
            ):
                entry = dict(
                    profile,
                    verified=True,
                    **{k: v for k, v in edits.items() if k != "verified"},
                )
                entry.update(edits)
                raw = json.dumps(
                    {"schema_version": 1, "hook_api": 1, "profiles": [entry]}
                ).encode()
                with self.subTest(edits=edits), self.assertRaises(ValueError):
                    mod.parse_catalog(raw)

    def test_wrong_architecture_and_outside_image_rejected(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe, profile = self.fixture(root)
            profile["assistant_predicate_rva"] = 0x10000000
            with patch.object(mod, "fetch_catalog", return_value=self.catalog(profile)):
                self.assertIsNone(mod.resolve(exe, root / "cache.json", None)[0])
            data = bytearray(exe.read_bytes())
            data[132:134] = (0x8664).to_bytes(2, "little")
            exe.write_bytes(data)
            profile["assistant_predicate_rva"] = 0x1000
            profile["exe_sha256"] = hashlib.sha256(data).hexdigest()
            with patch.object(mod, "fetch_catalog", return_value=self.catalog(profile)):
                self.assertIsNone(mod.resolve(exe, root / "cache.json", None)[0])

    def test_cache_write_failure_still_uses_valid_download(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe, profile = self.fixture(root)
            with (
                patch.object(mod, "fetch_catalog", return_value=self.catalog(profile)),
                patch.object(
                    mod, "save_cache", side_effect=PermissionError("read only")
                ),
            ):
                result = mod.resolve(exe, root / "cache.json", None)
            self.assertEqual(result[0], profile)

    def test_bundled_profile_works_without_network_or_cache(self):
        mod = self.module()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            exe, profile = self.fixture(root)
            with patch.object(
                mod, "fetch_catalog", side_effect=TimeoutError("timeout")
            ):
                result = mod.resolve(exe, root / "cache.json", profile)
            self.assertEqual(result[0], profile)
            self.assertIn("内置配置", result[2])

    def test_published_catalog_matches_bundled_profile(self):
        mod = self.module()
        profiles = mod.parse_catalog((ROOT / "adaptations.json").read_bytes())
        bundled = json.loads((ROOT / "compatibility.json").read_text(encoding="utf-8"))
        self.assertIn(bundled, profiles)

    def test_rejects_oversize_duplicates_and_future_hook_api(self):
        mod = self.module()
        for raw in (
            b" " * (mod.MAX_BYTES + 1),
            b"[" * 2000 + b"]" * 2000,
            b'{"schema_version":1,"schema_version":1,"hook_api":1,"profiles":[]}',
            b'{"schema_version":1,"hook_api":2,"profiles":[]}',
        ):
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                mod.parse_catalog(raw)


if __name__ == "__main__":
    unittest.main()
