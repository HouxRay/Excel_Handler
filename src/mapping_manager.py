"""映射持久化管理：MATCH_DICT 和键盘映射的加载/保存/重置"""
import json
from PyQt5.QtCore import QSettings


def get_default_match_dict() -> dict:
    """返回硬编码的 MATCH_DICT 默认值"""
    return {
        "s": "胜",
        "ss": "胜胜",
        "rs": "让胜",
        "f": "负",
        "rf": "让负",
        "p": "平",
        "rp": "让平",
        "sp": "双平",
        "q": "平",
        "rq": "让平",
        "sq": "双平",
        "fsf": "分胜负",
    }


def get_match_dict() -> dict:
    """从 QSettings 加载 MATCH_DICT，无则返回默认值"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    raw = settings.value("mappings/match_dict")
    if raw and isinstance(raw, str):
        try:
            pairs = json.loads(raw)
            if isinstance(pairs, list):
                return {k: v for k, v in pairs}
        except (json.JSONDecodeError, ValueError):
            pass
    return get_default_match_dict()


def save_match_dict(d: dict):
    """保存 MATCH_DICT 到 QSettings"""
    pairs = [[k, v] for k, v in d.items()]
    settings = QSettings("config.ini", QSettings.IniFormat)
    settings.setValue("mappings/match_dict", json.dumps(pairs, ensure_ascii=False))


def get_default_keyboard_mappings() -> dict:
    """返回硬编码的键盘映射默认值"""
    return {" ": "0", "`": "0"}


def get_keyboard_mappings() -> dict:
    """从 QSettings 加载键盘映射，无则返回默认值"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    raw = settings.value("mappings/keyboard")
    if raw and isinstance(raw, str):
        try:
            pairs = json.loads(raw)
            if isinstance(pairs, list):
                return {k: v for k, v in pairs}
        except (json.JSONDecodeError, ValueError):
            pass
    return get_default_keyboard_mappings()


def save_keyboard_mappings(d: dict):
    """保存键盘映射到 QSettings"""
    pairs = [[k, v] for k, v in d.items()]
    settings = QSettings("config.ini", QSettings.IniFormat)
    settings.setValue("mappings/keyboard", json.dumps(pairs, ensure_ascii=False))


def apply_keyboard_mappings(text: str, mappings: dict = None) -> str:
    """对文本应用所有键盘映射替换"""
    if mappings is None:
        mappings = get_keyboard_mappings()
    for char, replacement in mappings.items():
        text = text.replace(char, replacement)
    return text
