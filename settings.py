"""Validated, local navigation preferences; no process access."""

import json
import os
import tempfile
from pathlib import Path

NAV_ITEMS = {
    "智能助理": [],  # Uses the separately verified navigation predicate.
    "邮件": ["mail_plugin_op", "mail_plugin_op_layout", "bzmail", "bzmail_layout"],
    "文档": ["wxwork_doc_op", "wxwork_doc_op_layout", "mail_doc_op", "tencent_doc_op"],
    "日程": ["calendar_op", "calendar_op_layout"],
    "待办": ["todo_op", "todo_layout"],
    "会议": ["tm_meeting_op", "tm_meeting_op_layout", "meeting_op"],
    "智能文档": ["smart_sheet_op", "smart_sheet_op_layout"],
    "智能总结": ["ai_summary_op", "ai_summary_op_layout"],
    "工作台": ["work_op"],
    "通讯录": ["org_op", "org_op_layout"],
    "微盘": ["qy_disk_op", "qy_disk_op_layout"],
    "高级功能": ["advanced_func_op"],
}


def parse_config(raw):
    if len(raw) > 16384:
        raise ValueError("config.json 超过 16 KB，请只保留隐藏名单。")

    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"配置字段重复：{key}")
            obj[key] = value
        return obj

    obj = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object)
    if not isinstance(obj, dict) or "hide" not in obj or set(obj) - {"hide", "paths"}:
        raise ValueError("配置必须包含 hide 数组，可选 paths 对象。")
    paths = obj.get("paths", {})
    if not isinstance(paths, dict) or set(paths) - {"wecom", "python"}:
        raise ValueError("paths 只支持 wecom 和 python 字段。")
    if any(not isinstance(value, str) for value in paths.values()):
        raise ValueError("路径必须是字符串，留空表示自动检测。")
    items = obj["hide"]
    if not isinstance(items, list) or any(not isinstance(x, str) for x in items):
        raise ValueError("hide 必须是中文项目名称组成的数组。")
    unknown = [x for x in items if x not in NAV_ITEMS]
    if unknown:
        raise ValueError(
            "不支持的项目：" + "、".join(unknown) + "。可选：" + "、".join(NAV_ITEMS)
        )
    if len(set(items)) != len(items):
        raise ValueError("隐藏名单有重复项目，请删除重复名称。")
    return {
        "assistant": "智能助理" in items,
        "controls": [name for item in items for name in NAV_ITEMS[item]],
        "items": items,
        "paths": paths,
    }


def write_config(path, items, paths):
    raw = (
        json.dumps({"hide": items, "paths": paths}, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    parse_config(raw)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".config-", suffix=".tmp", delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(raw)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


class ConfigWatcher:
    """Apply only validated snapshots; a failed edit never clears active settings."""

    def __init__(self, path):
        self.path = path
        self.last_raw = path.read_bytes()
        self.current = parse_config(self.last_raw)
        self.last_error = None

    def poll(self, apply, log):
        try:
            raw = self.path.read_bytes()
            if raw == self.last_raw:
                self.last_error = None
                return
            candidate = parse_config(raw)
            apply(candidate)
            paths_changed = candidate["paths"] != self.current["paths"]
            self.current = candidate
            self.last_raw = raw
            self.last_error = None
            log(
                "配置已加载；隐藏："
                + ("、".join(candidate["items"]) or "无")
                + "。导航下次刷新时生效。"
            )
            if paths_changed:
                log("路径设置已保存；新路径在下次启动时使用，当前进程不切换。")
        except Exception as error:
            message = str(error)
            if message != self.last_error:
                log("配置未应用，保留上一次有效设置：" + message)
                self.last_error = message
