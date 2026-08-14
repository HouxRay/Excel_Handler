"""AI 编排模块 — HTML/文本 → AI → 结构化预测结果"""
import os

from src import ai_client
from src import ai_parser


def extract_predictions_from_html(html_file_path: str, excel_path: str = None,
                                  sheet_name: str = None, mode: str = 'jc') -> dict:
    """HTML 文件 → AI 结构化预测结果。

    excel_path/sheet_name: 提供则加载白名单约束 AI 输出编号
    mode: 'jc' 或 'bd'，决定白名单类型和提示词
    Returns: {"predictions": [...], "raw": "...", "method": "json"|"line"}
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

    # 若提供 Excel，加载白名单 + 目标日期，用白名单提示词
    if excel_path:
        from src import ai_alignment
        if mode == 'bd':
            whitelist = ai_alignment.load_bd_whitelist(excel_path, sheet_name)
        else:
            whitelist = ai_alignment.load_excel_whitelist(excel_path, sheet_name)
        target_date = ai_alignment.detect_target_date(markdown_text)
        messages = ai_client.build_messages_with_whitelist(
            markdown_text, whitelist, target_date, mode)
        response_text = ai_client.call_deepseek(messages)
        # 后端校验：过滤 AI 幻觉补全的编号
        result = ai_parser.parse_ai_result(response_text)
        text_codes = ai_alignment.extract_codes_from_text(html_content)
        result['predictions'] = ai_alignment.filter_hallucinations(
            result.get('predictions', []), text_codes, whitelist)
        return result

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


def extract_predictions_from_image(image_path: str) -> dict:
    """图片 → OCR → AI → 结构化结果"""
    from src import ocr_handler
    return ocr_handler.extract_predictions_from_image(image_path)
