"""AI 配置管理：API Key、模型、基址，存 config.ini"""
from PyQt5.QtCore import QSettings

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE = "https://api.deepseek.com"


def get_api_key() -> str:
    """读取 AI API Key（config.ini [ai] 段）"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    return settings.value("ai/api_key", "") or ""


def get_model() -> str:
    """读取 AI 模型名"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    return settings.value("ai/model", DEFAULT_MODEL) or DEFAULT_MODEL


def get_base_url() -> str:
    """读取 AI API 基址"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    return settings.value("ai/base_url", DEFAULT_BASE) or DEFAULT_BASE


def save_ai_config(api_key: str, model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE):
    """保存 AI 配置到 config.ini"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    settings.setValue("ai/api_key", api_key)
    settings.setValue("ai/model", model)
    settings.setValue("ai/base_url", base_url)
