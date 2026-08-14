"""AI 配置管理：API Key（加密存储）、模型、基址，存 config.ini"""
import base64
import hashlib
import os
import uuid

from PyQt5.QtCore import QSettings

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE = "https://api.deepseek.com"
_ENC_PREFIX = "enc:"  # 加密值前缀，用于区分明文/密文


def _machine_key() -> bytes:
    """基于机器标识的混淆密钥（绑定本机，跨机器无法解密）"""
    raw = f"{uuid.getnode()}|{os.environ.get('COMPUTERNAME', '')}"
    return hashlib.sha256(raw.encode('utf-8')).digest()


def _xor_encrypt(plain: str) -> str:
    """简单 XOR 混淆 + base64，绑定机器"""
    key = _machine_key()
    data = plain.encode('utf-8')
    enc = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return _ENC_PREFIX + base64.b64encode(enc).decode('ascii')


def _xor_decrypt(cipher: str) -> str:
    """解密 XOR 混淆值"""
    key = _machine_key()
    try:
        data = base64.b64decode(cipher)
        dec = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return dec.decode('utf-8')
    except Exception:
        return ""


def get_api_key() -> str:
    """读取 AI API Key。兼容旧明文（无 enc: 前缀按明文返回）"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    raw = settings.value("ai/api_key", "") or ""
    if not raw:
        return ""
    if raw.startswith(_ENC_PREFIX):
        return _xor_decrypt(raw[len(_ENC_PREFIX):])
    return raw  # 旧明文，兼容


def save_api_key(plain_key: str):
    """加密保存 API Key（一次性可见：存后不可读明文）"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    if plain_key:
        settings.setValue("ai/api_key", _xor_encrypt(plain_key))
    # 空则不写入（保留原值）


def clear_api_key():
    """删除 API Key"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    settings.setValue("ai/api_key", "")


def has_api_key() -> bool:
    """是否已配置 API Key"""
    return bool(get_api_key())


def get_model() -> str:
    """读取 AI 模型名"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    return settings.value("ai/model", DEFAULT_MODEL) or DEFAULT_MODEL


def get_base_url() -> str:
    """读取 AI API 基址"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    return settings.value("ai/base_url", DEFAULT_BASE) or DEFAULT_BASE


def save_ai_config(api_key: str, model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE):
    """保存 AI 配置。api_key 为空时保留原值（不清空）"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    if api_key:
        settings.setValue("ai/api_key", _xor_encrypt(api_key))
    settings.setValue("ai/model", model)
    settings.setValue("ai/base_url", base_url)
