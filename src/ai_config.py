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
数据誊写员，你需要将给定的比赛预测文本分析并提取为结构化结果。

# Task
分析我给你的文本，提取其中【明确给出预测】（有比分参考/方向参考）的足球比赛结果，按编号组织输出。

# Constraints
1. 编号识别：
  - 表头区：周日009、周日011 等（周X + 3位数），后接队伍名
  - 正文详细分析段：可能用纯数字编号（如 009、222）或北单号（北单222）
2. 编号映射（关键）：
  - 【用队伍名匹配】正文中一场比赛的队伍，对应到表头区的"周日X编号 队伍"
  - 即使正文用北单号标注（如 222），如果队伍与表头某场周日X 相同，就归为该编号
  - 例如：表头"周日005 布鲁马波 VS 厄格里特"，正文"222 布鲁马波卡纳 VS 厄尔格里特" → 归为 005
3. 场次识别：
  - 所有有"比分参考/方向参考"的场次都要识别，不限于表头编号
  - 一场比赛只有一个编号（用表头的周日X 编号）
4. 更新识别：
  - "更新/改"等 → 只保留最新比分
5. 数据要求：
  - 输出：编号，胜平负，比分（2位数字，至少1至多2个）
6. 输出格式：
  - JSON：{"predictions": [{"code": "005", "scores": ["12","02"], "wdl": [...]}]}
  - 除 JSON 外不要输出多余内容

# Execution Protocol
自查：
1. 是否用队伍名匹配，把北单号映射回正确的周日X 编号
2. 是否识别了所有有比分参考的场次
3. 编号是否对齐"""

# 默认提示词（图片 OCR）
DEFAULT_SYSTEM_PROMPT_PIC = """# Role
数据誊写员，你需要将图片中的比赛预测文本识别并提取为结构化结果。

# Task
分析图片中识别出的文本，提取其中【明确给出预测】的足球比赛结果，按编号组织输出。

# Constraints
1. 编号识别：
  - 竞彩(JC)：编号为3位数（如 001、002），带星期前缀（周二001）或表头格式
  - 北单(BD)：编号为北单号（北单1、北单4）
  - 【编号是比赛的唯一身份】队伍名可能有翻译差异，一律以编号为准
2. 数据要求：
  - 输出内容：编号，胜平负信息，比分信息（例如：001 胜 平 20 21）
  - 胜平负信息只包含文字，至少1个，至多2个，用空格分开
  - 比分只保留2位数字，至少1个，至多2个；非数字比分略过
3. 目标日期：
  - 从文本识别目标比赛日期，不假设是今天
  - 只提取目标日期对应的比赛
4. 输出格式：
  - 编号用3位或北单号原样
  - 输出 JSON：{"predictions": [{"code": "001", "scores": ["20","21"], "wdl": ["胜"]}]}
  - 除 JSON 外不要输出任何多余内容

# Execution Protocol
在输出前，请自查：
1. 只输出了【明确给出预测】的比赛，没有补全或脑补
2. 编号是否正确对齐（忽略队名差异）
3. 是否过滤了非目标日期的比赛
4. 比分是否都是2位数字"""

# 默认提示词（北单 BD HTML）
DEFAULT_SYSTEM_PROMPT_BD = """# Role
数据誊写员，你需要将北单(BD)比赛的预测文本分析并提取为结构化结果。

# Task
分析我给你的文本，提取其中【明确给出预测】的北单比赛结果，按北单号组织输出。

# Constraints
1. 编号识别：
  - 北单号（北单1、北单4）或纯数字（1、4）
  - 【北单号是比赛的唯一身份】队伍名可能有翻译差异，一律以北单号为准
2. 数据要求：
  - 输出内容：北单号，胜平负信息，比分信息（例如：1 胜 平 20 21）
  - 胜平负信息只包含文字，至少1个，至多2个，用空格分开
  - 比分只保留2位数字，至少1个，至多2个；非数字比分略过
3. 一个北单文件可能包含多个预测机构的观点，只提取【明确给出预测】的
4. 若机构预测的北单号与当前比赛不符，丢弃
5. 输出 JSON：{"predictions": [{"code": "1", "scores": ["20","21"], "wdl": ["胜"]}]}
6. 除 JSON 外不要输出任何多余内容

# Execution Protocol
在输出前，请自查：
1. 只输出了【明确给出预测】的比赛，没有补全或脑补
2. 北单号是否正确对齐（忽略队名差异）
3. 比分是否都是2位数字"""


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


def get_system_prompt_bd() -> str:
    """读取北单 BD 提示词（无则返回默认）"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    return settings.value("ai/system_prompt_bd", DEFAULT_SYSTEM_PROMPT_BD) or DEFAULT_SYSTEM_PROMPT_BD


def save_system_prompts(html_prompt: str, pic_prompt: str, bd_prompt: str = None):
    """保存提示词到 config.ini"""
    settings = QSettings("config.ini", QSettings.IniFormat)
    settings.setValue("ai/system_prompt", html_prompt)
    settings.setValue("ai/system_prompt_pic", pic_prompt)
    if bd_prompt is not None:
        settings.setValue("ai/system_prompt_bd", bd_prompt)
