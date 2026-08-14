"""AI 配置管理：API Key（加密存储）、模型、基址，存 config.ini"""
import base64
import hashlib
import os
import uuid

from PyQt5.QtCore import QSettings

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE = "https://api.deepseek.com"
_ENC_PREFIX = "enc:"  # 加密值前缀，用于区分明文/密文

# 默认提示词（HTML/文本）
DEFAULT_SYSTEM_PROMPT = """# Role
数据誊写员，你需要将给你的文本数据进行分析并返回

# Task
请分析我给你的所有文本，这些文本是某些运动的比分预测，你需要将当天的足球相关赛事的比分按照规定格式分析并返回

# Constraints
1. 判断今天是星期几，然后将当天的比分进行总结并返回
2. 数据要求：你需要输出的内容有：编号，胜平负信息，比分信息（例如：001 胜 平 20 21）
3. 格式需求：
  - 编号要是3位数的（例如001， 002）
  - 胜平负信息只包含文字，至少1个，至多2个，用空格分开（例如 让胜 或 胜 负）
  - 比分只输出2个数字（例如：11 00），且比分至少输出1个，至多2个，如果遇到非数字比分，略过
  - 输出为：编号 胜平负 比分预测
4. 输出格式：
  - Part 1 [输出结果]：当前图片比分预测
  - 除以上部分外，不要输出任何多余的对话

# Execution Protocol
在输出前，请自查：
1. 是否查看的是今天的比分内容
2. 是否将所有胜平负信息与比分信息按照规定格式输出
3. 是否查看的是足球信息，而非其他信息"""

# 默认提示词（图片 OCR）
DEFAULT_SYSTEM_PROMPT_PIC = """# Role
数据誊写员，你需要将图片中所需要的数据进行誊写并返回

# Task
请分析我给你的所有文本，这些文本是某些运动的比分预测，你需要将当天的足球相关赛事的比分按照规定格式誊写

# Constraints
1. 判断今天是星期几：
  - 你需要判断今天是星期几，然后将当天的比分进行总结并返回
2. 数据要求：
  - 你需要输出的内容有：编号，胜平负信息，比分信息（例如：001 胜 平 20 21）
3. 格式需求：
  - 你输出的编号要是3位数的（例如001， 002）。
  - 胜平负信息只包含文字，至少1个，至多2个，用空格分开（例如 让胜 或 胜 负）
  - 比分只输出2个数字（例如：11 00），且比分至少输出1个，至多2个，如果遇到非数字比分，略过。
  - 输出为：编号 胜平负 比分预测（xxx xx xx xx xx）
4. 输出格式：
  - Part 1 [输出结果]：当前图片比分预测
  - 除以上部分外，不要输出任何多余的对话。

# Execution Protocol
在输出前，请自查：
1. 是否查看的是今天的比分内容
2. 是否将所有胜平负信息与比分信息按照规定格式输出
3. 是否查看的是足球信息，而非其他信息"""


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


def get_system_prompt() -> str:
    """读取 HTML/文本提示词（无则返回默认）"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    return settings.value("ai/system_prompt", DEFAULT_SYSTEM_PROMPT) or DEFAULT_SYSTEM_PROMPT


def get_system_prompt_pic() -> str:
    """读取图片 OCR 提示词（无则返回默认）"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    return settings.value("ai/system_prompt_pic", DEFAULT_SYSTEM_PROMPT_PIC) or DEFAULT_SYSTEM_PROMPT_PIC


def save_system_prompts(html_prompt: str, pic_prompt: str):
    """保存提示词到 config.ini"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    settings.setValue("ai/system_prompt", html_prompt)
    settings.setValue("ai/system_prompt_pic", pic_prompt)
