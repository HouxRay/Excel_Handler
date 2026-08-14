"""
AI 客户端模块 — HTML → Markdown → Deepseek API 调用
从 AI/ai_extractor.py 迁移改造：去掉硬编码 Key，改为从 config.ini 读取。
"""
import importlib
import os
import re
from datetime import datetime, timezone, timedelta
from openai import OpenAI

from src import ai_config

# 尝试导入 html2text
try:
    html2text = importlib.import_module("html2text")
    _HAS_HTML2TEXT = True
except ImportError:
    html2text = None
    _HAS_HTML2TEXT = False


# --- System Prompt ---
SYSTEM_PROMPT = """# Role
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


def _preprocess_html(html_content: str) -> str:
    """预处理 HTML：<font color="red">X</font> → <strong>X</strong>"""
    html_content = re.sub(
        r'<font\s+color\s*=\s*["\']\s*red\s*["\'][^>]*>',
        '<strong>',
        html_content,
        flags=re.IGNORECASE
    )
    html_content = html_content.replace('</font>', '</strong>')
    return html_content


def html_to_markdown(html_content: str) -> str:
    """将 HTML 文本转换为 Markdown"""
    if not _HAS_HTML2TEXT:
        # 回退：简单去除 HTML 标签
        text = re.sub(r'<br\s*/?>', '\n', html_content, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    html_content = _preprocess_html(html_content)

    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.ignore_links = True
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.protect_links = False
    converter.tables_bypass = False
    converter.skip_internal_links = True
    converter.mark_code = False
    converter.wrap_links = False
    converter.ignore_tables = False

    md = converter.handle(html_content)
    md = re.sub(r'\n{4,}', '\n\n\n', md)
    return md.strip()


def _beijing_weekday() -> str:
    """返回北京时区当前星期（如 "周三"）"""
    beijing = timezone(timedelta(hours=8))
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[datetime.now(beijing).weekday()]


def build_messages(markdown_text: str) -> list[dict]:
    """构建 Chat messages"""
    today = _beijing_weekday()
    user_text = (
        f"今天是{today}，请分析以下文本中的足球比赛预测，"
        f"提取所有{today}的比赛结果。\n\n"
        f"{markdown_text}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]


def call_deepseek(messages: list[dict], timeout: int = 120) -> str:
    """调用 Deepseek API（OpenAI 兼容 SDK），返回响应文本。

    API Key 从 config.ini 读取，未配置时抛异常。
    """
    api_key = ai_config.get_api_key()
    if not api_key:
        raise RuntimeError(
            "未配置 AI API Key\n请先在 config.ini 的 [ai] 段设置 ai/api_key，"
            "或在设置对话框中配置"
        )

    client = OpenAI(
        api_key=api_key,
        base_url=ai_config.get_base_url(),
        timeout=timeout,
    )

    response = client.chat.completions.create(
        model=ai_config.get_model(),
        messages=messages,
        temperature=0.7,
        max_tokens=4096,
        stream=False,
        reasoning_effort="medium",
        extra_body={},
    )

    # V4 thinking 模式下 content 可能为 None，退到 reasoning_content
    content = response.choices[0].message.content
    if content is None:
        content = getattr(response.choices[0].message, 'reasoning_content', None) or ""
    return content


def call_ai(markdown_text: str) -> str:
    """简化入口：Markdown → Deepseek → 响应文本"""
    messages = build_messages(markdown_text)
    return call_deepseek(messages)
