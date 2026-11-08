"""AI 配置管理：API Key（加密存储）、模型、基址，存 config.ini"""
import base64
import hashlib
import logging
import os
import uuid

from PyQt5.QtCore import QSettings

DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE = "https://api.deepseek.com"
logger = logging.getLogger(__name__)

_ENC_PREFIX = "enc:"  # 加密值前缀，用于区分明文/密文

# 图片识别路径（配置键 ai/image_pipeline）
#   vision —— 图片经 base64 直接送 AI 原生视觉理解（默认；实测比 OCR 快约 4.6 倍）
#   ocr    —— 本地 RapidOCR 识别为文本后再送 AI（原有行为，可离线兜底）
IMAGE_PIPELINES = ("vision", "ocr")
DEFAULT_IMAGE_PIPELINE = "vision"

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

# 默认提示词（图片）
# 旧版默认值：仅用于自动迁移（见 get_system_prompt_pic），**勿删**
LEGACY_SYSTEM_PROMPT_PIC = """# Role
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

DEFAULT_SYSTEM_PROMPT_PIC = """# Role
数据誊写员，你需要将图片中的比赛预测表格识别并提取为结构化结果。

# Task
分析图片中的表格，逐行提取【明确给出预测】的足球比赛，按编号组织输出。

# Constraints
1. 编号识别：
  - 竞彩(JC)：编号为3位数（如 001、002），表头常带星期前缀（周日001）
  - 北单(BD)：编号为北单号（北单1、北单4）
  - 【编号是比赛的唯一身份】队伍名可能有翻译差异，一律以编号为准
2. 胜负平（关键，极易取错列）：
  - 只取「胜负平」列（**队伍列右边的那一列**），其值形如：主胜 / 主负 / 平 /
    让胜（+1）/ 让平（-1）/ 平让平（-1）/ 主负+平
  - 【绝对不要取「半全场」列】半全场的值是两个字直接相连：平胜、负平、胜胜、
    平平、负负、胜平… 这些值一律不要放进 wdl
  - 对照反例：若某行「胜负平」列是「主负+平」、其右边的「半全场」列是「负负，负平」，
    正确的 wdl 是 ["负","平"]（来自胜负平列）；写成 ["负负","负平"] 就是把半全场
    当成了胜负平，属于错误
  - wdl 只允许这 7 个取值：胜、负、平、让平、双平、让胜、让负。**不允许出现数字**
    · 「主胜」写成「胜」，「主负」写成「负」
    · 让球数（+1）（-1）一律去掉
  - 一格里有多个取值时要拆开，最多 2 个：
    · 「平让平」→ ["平", "让平"]
    · 「让平让负」→ ["让平", "让负"]
    · 「主负+平」→ ["负", "平"]
  - 确实取不到合法胜负平时，wdl 用空数组 []，不要猜
3. 比分：
  - 取「比分」列，只保留2位数字，至少1个，至多2个；非数字比分略过
4. 目标日期：
  - 从图中识别目标比赛日期，不假设是今天；只提取目标日期对应的比赛
5. 输出格式：
  - 编号用3位或北单号原样
  - 输出 JSON：{"predictions": [{"code": "001", "scores": ["10","11"], "wdl": ["让胜"]}]}
  - 除 JSON 外不要输出任何多余内容

# Execution Protocol
在输出前，请自查：
1. wdl 里的值是否【只有那 7 个】、且【不含任何数字】
2. 是否误把「半全场」列（平胜、负平、胜胜…）当成了胜负平 —— 若是，改回「胜负平」列
3. 一格里写了两个取值时是否已拆成最多 2 个
4. 只输出了【明确给出预测】的比赛，没有补全或脑补
5. 比分是否都是2位数字
6. 是否过滤了非目标日期的比赛"""

# 默认提示词（北单 BD HTML）
DEFAULT_SYSTEM_PROMPT_BD = """# Role
数据誊写员，你需要将北单(BD)比赛的预测文本分析并提取为结构化结果。

# Task
分析我给你的文本，提取其中【明确给出预测】的北单比赛比分，按北单号组织输出。

# Constraints
1. 编号识别：
  - 北单号（北单1、北单3）或纯数字（1、3）
  - 【北单号是比赛的唯一身份】队伍名可能有翻译差异，一律以北单号为准
2. 输出格式（关键）：
  - 输出为：机构名：北单号 比分1 比分2 ...
  - 每个预测机构一行，输出前加上该机构的名称
  - 相同预测机构比分并排输出，不同预测机构分开输出
3. 比分要求：
  - 只输出2位数字比分（例如：01、12、21）
  - 比分个数没有上限（如 01 12 21 00 11）
  - 比分会以 "x-x"、"x:x"、"xx" 形式给出，不会以 "x.x" 形式，注意不要誊写错误
  - 非数字比分略过
  - 胜平负信息可以识别但不作为主要输出
4. 多组比赛区分（关键）：
  - 部分预测会包含多组比赛（北单1、北单2、北单3...），必须区分编号对应的比赛
  - 只输出【当前目标北单号】对应的比赛比分，其他编号的比分不输出
  - 注意检查编号与队伍的匹配关系，避免编号与数据、比分预测不匹配
5. 若某机构的预测不是当前目标北单号的比赛，丢弃

# Execution Protocol
在输出前，请自查：
1. 是否找到了正确的比分（不是小数、正负数等错误数据）
2. 是否只输出了【当前目标北单号】的比分，没有混入其他比赛的比分
3. 是否检查了编号与队伍的匹配关系
4. 每个机构是否单独一行，机构名前缀是否正确"""


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


def _env_api_key() -> str:
    """从环境变量读取 API Key（**容器 / 无界面部署的正路**）

    为什么必须有这条路径：``_xor_encrypt`` 用 ``MAC + COMPUTERNAME`` 做混淆密钥，
    **绑定本机**。桌面版在 Windows 上保存的 Key，拷到 Linux 容器里**解不开**
    （容器内 ``COMPUTERNAME`` 为空、MAC 也不同），只能靠环境变量传明文。

    支持的变量名（按优先级）：``APP_AI_KEY`` / ``DEEPSEEK_KEY`` / ``OPENAI_API_KEY``
    """
    for name in ("APP_AI_KEY", "DEEPSEEK_KEY", "OPENAI_API_KEY"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def get_api_key() -> str:
    """读取 AI API Key。优先级：环境变量 > 加密存储 > 旧明文"""
    env_key = _env_api_key()
    if env_key:
        return env_key
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


def get_image_pipeline() -> str:
    """读取图片识别路径：'vision'（原生视觉，默认）或 'ocr'（本地 OCR）

    非法值/未配置一律回退到默认值，避免配置写坏导致图片链路不可用。
    """
    settings = QSettings("config.ini", QSettings.IniFormat)
    value = (settings.value("ai/image_pipeline", DEFAULT_IMAGE_PIPELINE) or "").strip().lower()
    return value if value in IMAGE_PIPELINES else DEFAULT_IMAGE_PIPELINE


def save_image_pipeline(mode: str):
    """保存图片识别路径；非 IMAGE_PIPELINES 内的值忽略（保留原配置）"""
    if mode in IMAGE_PIPELINES:
        QSettings("config.ini", QSettings.IniFormat).setValue("ai/image_pipeline", mode)


# --- 提示词存储：外部 txt 优先，内置默认兜底 -------------------------------
#
# **为什么不再只写 config.ini**：QSettings 会把多行 Markdown 转义成 \xNN 形式
# （形如 system_prompt="# Role \x6570\x636e..."），外部既读不懂也无法 diff。
# 现在提示词以独立文本文件保存在 <软件目录>/prompts/ 下，可直接用编辑器修改，
# 改完重启程序即生效；文件缺失或为空时回退到内置默认值，保证任何情况下都能工作。

PROMPT_FILES = {
    "system_prompt": "system_prompt.txt",
    "system_prompt_pic": "system_prompt_pic.txt",
    "system_prompt_bd": "system_prompt_bd.txt",
}

PROMPT_DEFAULTS = {
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "system_prompt_pic": DEFAULT_SYSTEM_PROMPT_PIC,
    "system_prompt_bd": DEFAULT_SYSTEM_PROMPT_BD,
}


def prompts_dir() -> str:
    """提示词目录：软件目录下的 ``prompts/``（打包后即 exe 同目录）"""
    from src.common import app_paths

    return app_paths.runtime_subdir("prompts")


def prompt_file(key: str) -> str:
    """某个提示词对应的 txt 文件路径"""
    return os.path.join(prompts_dir(), PROMPT_FILES[key])


def read_prompt_file(key: str) -> str:
    """读取 txt；不存在 / 空白 / 读失败 → 返回空串（调用方回退内置默认）"""
    path = prompt_file(key)
    try:
        if not os.path.isfile(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return "" if not text.strip() else text
    except Exception:
        logger.exception(f"读取提示词文件失败，将回退内置默认: {path}")
        return ""


def write_prompt_file(key: str, text: str) -> bool:
    """写入 txt；内容为空白则删除该文件（等于"恢复默认"）"""
    path = prompt_file(key)
    try:
        os.makedirs(prompts_dir(), exist_ok=True)
        if not (text or "").strip():
            if os.path.isfile(path):
                os.remove(path)
            return True
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return True
    except Exception:
        logger.exception(f"写入提示词文件失败: {path}")
        return False


def _collapse_ws(text: str) -> str:
    """把所有空白折叠成单个空格，用于"是否仍是旧版默认提示词"的宽松比较。

    QSettings(IniFormat) 读回多行文本时可能把换行变成空格，直接字符串相等会失效。
    """
    return " ".join((text or "").split())


def _legacy_prompt(key: str) -> str:
    """从 config.ini 读旧版提示词（仅用于兼容迁移）"""
    try:
        return QSettings("config.ini", QSettings.IniFormat).value(f"ai/{key}", "") or ""
    except Exception:
        return ""


def _effective_prompt(key: str) -> str:
    """当前生效值：txt → config.ini（旧版兼容）→ 内置默认

    旧版默认提示词（``LEGACY_SYSTEM_PROMPT_PIC``）不算用户自定义，直接回退新默认
    —— 否则升级后新增的规则不会生效。
    """
    text = read_prompt_file(key)
    if text:
        return text
    stored = _legacy_prompt(key)
    if stored and _collapse_ws(stored) != _collapse_ws(LEGACY_SYSTEM_PROMPT_PIC):
        return stored
    return PROMPT_DEFAULTS[key]


def clear_legacy_prompt_keys():
    """清掉 config.ini 里的旧提示词键（迁移完成后调用）"""
    try:
        settings = QSettings("config.ini", QSettings.IniFormat)
        for key in PROMPT_FILES:
            settings.remove(f"ai/{key}")
    except Exception:
        logger.exception("清理 config.ini 旧提示词键失败")


def ensure_prompt_files() -> list:
    """自举：把缺失的提示词导出成 txt（用户无需手抄现有内容）

    Returns: 本次新创建的文件路径列表
    """
    created = []
    for key in PROMPT_FILES:
        if read_prompt_file(key):
            continue
        if write_prompt_file(key, _effective_prompt(key)):
            created.append(prompt_file(key))
    if created:
        logger.info(f"已导出提示词文件 {len(created)} 个: {created}")
    return created


def migrate_legacy_prompts() -> list:
    """把 config.ini 里的旧提示词迁移成 txt，随后清掉旧键

    仅在 txt 尚不存在时迁移，避免覆盖用户已经手工改过的文件。
    """
    migrated = []
    for key in PROMPT_FILES:
        stored = _legacy_prompt(key)
        if not stored.strip():
            continue
        if read_prompt_file(key):
            continue
        if write_prompt_file(key, stored):
            migrated.append(prompt_file(key))
    if migrated:
        clear_legacy_prompt_keys()
        logger.info(f"旧提示词已迁移到 txt: {migrated}")
    return migrated


def get_system_prompt() -> str:
    """HTML / 文本模式提示词（txt → 旧配置 → 内置默认）"""
    return _effective_prompt("system_prompt")


def get_system_prompt_pic() -> str:
    """图片模式提示词（txt → 旧配置 → 内置默认）"""
    return _effective_prompt("system_prompt_pic")


def get_system_prompt_bd() -> str:
    """结构化数据源模式提示词（txt → 旧配置 → 内置默认）"""
    return _effective_prompt("system_prompt_bd")


def save_system_prompts(html_prompt: str, pic_prompt: str, bd_prompt: str = None):
    """保存提示词到 ``prompts/*.txt``（不再写 config.ini 的转义串）"""
    write_prompt_file("system_prompt", html_prompt)
    write_prompt_file("system_prompt_pic", pic_prompt)
    if bd_prompt is not None:
        write_prompt_file("system_prompt_bd", bd_prompt)
    clear_legacy_prompt_keys()


# --- 目标比赛日期管理（硬约束） ---
# 模块级内存变量：单次启动内可覆盖目标星期，重启自动重置
_override_weekday = None

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _get_beijing_weekday() -> str:
    """返回北京时区真实今天的星期"""
    from datetime import datetime, timezone, timedelta
    beijing = timezone(timedelta(hours=8))
    return WEEKDAYS[datetime.now(beijing).weekday()]


def get_target_weekday() -> str:
    """返回实际生效的目标星期（优先内存覆盖值，否则真实今天北京时区）"""
    return _override_weekday if _override_weekday else _get_beijing_weekday()


def set_target_weekday(wd: str):
    """设置目标星期覆盖值（仅内存，单次启动有效）"""
    global _override_weekday
    if wd in WEEKDAYS:
        _override_weekday = wd


def reset_target_weekday():
    """重置覆盖值，恢复真实今天（每次启动时调用）"""
    global _override_weekday
    _override_weekday = None
