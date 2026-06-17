"""
AI 比分预测提取器
独立模块，不依赖项目其他代码。HTML → Markdown → Deepseek API → 结构化输出。
"""
import importlib
import os
import re
import json
from datetime import datetime, timezone, timedelta
from openai import OpenAI

# 尝试导入 html2text；安装：pip install html2text
try:
    html2text = importlib.import_module("html2text")
    _HAS_HTML2TEXT = True
except ImportError:
    html2text = None
    _HAS_HTML2TEXT = False


KEY = "sk-6bfe21c6d68944119f3bf752bd546319"
# --- 配置 ---
API_KEY = os.environ.get("DEEPSEEK_API_KEY", KEY)
API_BASE = "https://api.deepseek.com"
MODEL = "deepseek-v4-flash"

# --- System Prompt（来自 Skill/HTML.md）---
SYSTEM_PROMPT = """# Role
数据誊写员，你需要将给你的文本数据进行分析并返回

# Task
请分析我给你的所有文本，这些文本是某些运动的比分预测，你需要将当天的足球相关赛事的比分按照规定格式分析并返回

# Constraints
1. 判断今天是星期几：
  - 你需要判断今天是星期几，然后将当天的比分进行总结并返回
2. 数据要求：
  - 你需要输出的内容有：编号，胜平负信息，比分信息（例如：001 胜 平 20 21）
3. 格式需求：
  - 你输出的编号要是3位数的（例如001， 002）。
  - 胜平负信息只包含文字，至少1个，至多2个，用空格分开（例如 让胜  或   胜 负）
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


def _preprocess_html(html_content: str) -> str:
    """预处理 HTML：<font color="red">X</font> → <strong>X</strong>"""
    # 处理 <font color="red"> ... </font>
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
    converter.body_width = 0          # 不自动换行
    converter.ignore_links = True
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.protect_links = False
    converter.tables_bypass = False   # 保留 table 转为 Markdown table
    converter.skip_internal_links = True
    converter.mark_code = False
    converter.wrap_links = False
    converter.ignore_tables = False

    md = converter.handle(html_content)
    # 清理多余空行
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
    """调用 Deepseek API（使用 OpenAI 兼容 SDK），返回响应文本"""
    if not API_KEY:
        raise RuntimeError(
            "请设置环境变量 DEEPSEEK_API_KEY\n"
            "例如: set DEEPSEEK_API_KEY=sk-xxxxx"
        )

    client = OpenAI(
        api_key=API_KEY,
        base_url=API_BASE,
        timeout=timeout,
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=4096,
        stream=False,
        reasoning_effort="medium",
        extra_body={}#"thinking": {"type": "enabled"}},
    )

    # V4 thinking 模式下 content 可能为 None，退到 reasoning_content
    content = response.choices[0].message.content
    if content is None:
        content = getattr(response.choices[0].message, 'reasoning_content', None) or ""

    return content


# 行解析正则: 编号（3位数字） + 胜平负（1-2个中文词） + 比分（1-2组2位数字）
_LINE_PATTERN = re.compile(
    r'(\d{3})\s+'                                   # 编号
    r'([一-龥]+(?:\s+[一-龥]+)?)\s+'  # 胜平负（1-2个）
    r'(\d{2}(?:\s+\d{2})?)'                          # 比分（1-2组）
)


def parse_response(response_text: str) -> dict:
    """
    解析 AI 响应为结构化 dict。

    返回格式：
    {
        "001": {"wdl": ["胜", "平"], "scores": ["20", "21"]},
        ...
    }
    """
    result = {}
    for line in response_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('Part'):
            continue
        match = _LINE_PATTERN.search(line)
        if match:
            code = match.group(1)
            wdl_part = match.group(2).strip()
            score_part = match.group(3).strip()

            wdl_list = wdl_part.split()
            score_list = score_part.split()

            # 过滤非 2 位数字的比分
            score_list = [s for s in score_list if re.fullmatch(r'\d{2}', s)]

            # 确保 1-2 个元素
            wdl_list = wdl_list[:2]
            score_list = score_list[:2]

            result[code] = {
                "wdl": wdl_list,
                "scores": score_list,
            }
    return result


def extract_predictions(html_file_path: str) -> dict:
    """主入口：HTML 文件 → 结构化比分预测"""
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    markdown_text = html_to_markdown(html_content)
    messages = build_messages(markdown_text)
    response_text = call_deepseek(messages)
    return parse_response(response_text)
