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


# --- System Prompt（从配置读取，默认见 ai_config.DEFAULT_SYSTEM_PROMPT） ---


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
    """构建 Chat messages（无白名单，兼容旧逻辑）"""
    today = _beijing_weekday()
    user_text = (
        f"今天是{today}，请分析以下文本中的足球比赛预测，"
        f"提取所有{today}的比赛结果。\n\n"
        f"{markdown_text}"
    )
    return [
        {"role": "system", "content": ai_config.get_system_prompt()},
        {"role": "user", "content": user_text},
    ]


def build_messages_with_whitelist(markdown_text: str, whitelist: dict,
                                  target_date: str = "", mode: str = 'jc') -> list[dict]:
    """带白名单的提示词构建（JC/BD 对齐）。

    whitelist: {编号: (队伍A, 队伍B)}
    mode: 'jc' 或 'bd'
    """
    from src import ai_prompts
    if mode == 'bd':
        return ai_prompts.build_bd_messages(markdown_text, whitelist, target_date)
    return ai_prompts.build_jc_messages(markdown_text, whitelist, target_date)


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
        max_tokens=8192,
        stream=False,
        # 禁用思维链：deepseek-v4-flash 默认思考会耗尽 token 导致 content 为空
        extra_body={'thinking': {'type': 'disabled'}},
    )

    # 若 content 为空（兜底），回退到 reasoning_content
    content = response.choices[0].message.content
    if not content:
        content = getattr(response.choices[0].message, 'reasoning_content', None) or ""
    return content


def call_ai(markdown_text: str) -> str:
    """简化入口：Markdown → Deepseek → 响应文本"""
    messages = build_messages(markdown_text)
    return call_deepseek(messages)
