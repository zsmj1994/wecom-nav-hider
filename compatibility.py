"""Fetch data-only, maintainer-verified profiles and match local binaries."""

import hashlib
import json
import os
import re
import struct
import tempfile
from urllib.request import Request, urlopen

from paths import find_dui

CATALOG_URL = (
    "https://raw.githubusercontent.com/zsmj1994/wecom-nav-hider/main/adaptations.json"
)
MAX_BYTES = 256 * 1024
FIELDS = {
    "version",
    "architecture",
    "exe_sha256",
    "dui_sha256",
    "assistant_predicate_rva",
    "navigation_return_rva",
    "control_name_offset",
    "control_parent_offset",
    "navigation_container",
}


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != FIELDS:
        raise ValueError("适配配置字段不符合当前启动器协议")
    if not isinstance(profile["version"], str) or not re.fullmatch(
        r"\d+(\.\d+){3}", profile["version"]
    ):
        raise ValueError("无效版本号")
    if (
        profile["architecture"] != "ia32"
        or profile["navigation_container"] != "auto_adjust_op_container"
    ):
        raise ValueError("当前拦截脚本不支持此架构或导航容器")
    for key in ("exe_sha256", "dui_sha256"):
        if not isinstance(profile[key], str) or not re.fullmatch(
            "[0-9a-f]{64}", profile[key]
        ):
            raise ValueError("无效 SHA-256")
    for key in (
        "assistant_predicate_rva",
        "navigation_return_rva",
        "control_name_offset",
        "control_parent_offset",
    ):
        value = profile[key]
        limit = 0x1000 if key.endswith("_offset") else 0x80000000
        if type(value) is not int or not 0 < value < limit:
            raise ValueError("无效 RVA 或控件偏移")
    return profile


def parse_catalog(raw):
    if len(raw) > MAX_BYTES:
        raise ValueError("适配目录过大")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("适配目录有重复字段")
            result[key] = value
        return result

    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except RecursionError as error:
        raise ValueError("适配目录嵌套过深") from error
    if (
        not isinstance(obj, dict)
        or set(obj) != {"schema_version", "hook_api", "profiles"}
        or type(obj["schema_version"]) is not int
        or obj["schema_version"] != 1
        or type(obj["hook_api"]) is not int
        or obj["hook_api"] != 1
    ):
        raise ValueError("适配目录协议不兼容，需要更新启动器")
    if not isinstance(obj["profiles"], list) or len(obj["profiles"]) > 256:
        raise ValueError("无效适配列表")
    profiles = []
    identities = set()
    for entry in obj["profiles"]:
        if not isinstance(entry, dict) or entry.get("verified") is not True:
            raise ValueError("适配条目未经确认")
        profile = validate_profile({k: v for k, v in entry.items() if k != "verified"})
        identity = (profile["exe_sha256"], profile["dui_sha256"])
        if identity in identities:
            raise ValueError("适配条目重复")
        identities.add(identity)
        profiles.append(profile)
    return profiles


def fetch_catalog():
    request = Request(
        CATALOG_URL,
        headers={"User-Agent": "WeComNavHider", "Accept": "application/json"},
    )
    with urlopen(request, timeout=3) as response:
        if response.geturl() != CATALOG_URL:
            raise ValueError("适配目录发生非预期跳转")
        return response.read(MAX_BYTES + 1)


def save_cache(path, raw):
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".compat-", suffix=".tmp", delete=False
        ) as output:
            name = output.name
            output.write(raw)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def image_identity(exe):
    with exe.open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        stream.seek(0)
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b"MZ":
            return digest.hexdigest(), None, 0
        stream.seek(struct.unpack_from("<I", dos, 60)[0])
        header = stream.read(84)
    if len(header) != 84 or header[:4] != b"PE\0\0":
        return digest.hexdigest(), None, 0
    machine = struct.unpack_from("<H", header, 4)[0]
    magic = struct.unpack_from("<H", header, 24)[0]
    return (
        digest.hexdigest(),
        "ia32" if (machine, magic) == (0x14C, 0x10B) else None,
        struct.unpack_from("<I", header, 80)[0],
    )


def resolve(exe, cache_path, bundled):
    candidates = []
    notes = []
    try:
        raw = fetch_catalog()
        candidates.extend((p, "GitHub") for p in parse_catalog(raw))
        try:
            save_cache(cache_path, raw)
        except OSError:
            notes.append("适配缓存无法写入")
    except (OSError, ValueError) as error:
        notes.append("GitHub 适配更新不可用：" + str(error))
        try:
            with cache_path.open("rb") as cache:
                candidates.extend(
                    (p, "本地缓存") for p in parse_catalog(cache.read(MAX_BYTES + 1))
                )
        except (OSError, ValueError):
            pass
    if bundled is not None:
        try:
            candidates.append((validate_profile(bundled), "内置配置"))
        except ValueError:
            pass
    digest, architecture, image_size = image_identity(exe)
    for profile, source in candidates:
        if profile["exe_sha256"] != digest or profile["architecture"] != architecture:
            continue
        if any(
            profile[key] >= image_size
            for key in ("assistant_predicate_rva", "navigation_return_rva")
        ):
            continue
        try:
            dll = find_dui(exe, profile["dui_sha256"])
        except (OSError, RuntimeError):
            continue
        return profile, dll, "；".join(notes + [f"使用{source}：{profile['version']}"])
    return (
        None,
        None,
        "；".join(notes + ["未找到匹配当前 EXE、界面库及架构的已验证适配配置"]),
    )
