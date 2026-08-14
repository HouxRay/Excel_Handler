"""AI 编排模块 — HTML/文本 → AI → 结构化预测结果"""
import os

from src import ai_client
from src import ai_parser


def extract_predictions_from_html(html_file_path: str) -> dict:
    """HTML 文件 → AI 结构化预测结果。

    Returns: {"predictions": [...], "raw": "...", "method": "json"|"line"}
    空结果时 predictions 为空列表，不报错。
    """
    if not html_file_path or not os.path.exists(html_file_path):
        return {
            "predictions": [],
            "raw": "",
            "warning": f"文件不存在: {html_file_path}",
        }

    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    markdown_text = ai_client.html_to_markdown(html_content)
    response_text = ai_client.call_ai(markdown_text)
    return ai_parser.parse_ai_result(response_text)


def extract_predictions_from_text(text: str) -> dict:
    """纯文本 → AI 结构化预测结果（OCR 等场景复用）"""
    if not text or not text.strip():
        return {
            "predictions": [],
            "raw": "",
            "warning": "输入文本为空",
        }

    response_text = ai_client.call_ai(text)
    return ai_parser.parse_ai_result(response_text)
