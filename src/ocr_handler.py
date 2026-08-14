"""
OCR 图片文字识别模块 — 图片 → 文本 → AI 结构化预测
从 AI/ocr_extractor.py 迁移改造：去掉硬依赖，复用 src/ai_client 与 src/ai_parser。
"""
import importlib.util
import os
import re
from datetime import datetime, timezone, timedelta

from src import ai_client, ai_parser, ai_config

# --- 配置 ---
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}
OCR_CONFIDENCE_THRESH = 0.3          # 置信度阈值，低于此值忽略
LINE_GROUP_THRESHOLD = 15            # Y坐标行分组阈值（像素）

# --- OCR 引擎检测与缓存 ---
_OCR_ENGINE = None
_OCR_READER = None


def _detect_ocr_engine() -> str | None:
    """自动检测可用的 OCR 引擎，优先级: rapidocr > easyocr"""
    global _OCR_ENGINE
    if _OCR_ENGINE:
        return _OCR_ENGINE

    if importlib.util.find_spec("rapidocr_onnxruntime") is not None:
        _OCR_ENGINE = "rapidocr"
    elif importlib.util.find_spec("easyocr") is not None:
        _OCR_ENGINE = "easyocr"
    else:
        _OCR_ENGINE = None
    return _OCR_ENGINE


def _get_ocr_reader():
    """惰性加载 OCR reader（模块级缓存复用）"""
    global _OCR_READER
    if _OCR_READER is not None:
        return _OCR_READER

    engine = _detect_ocr_engine()
    if engine == "easyocr":
        easyocr = __import__("easyocr")
        _OCR_READER = easyocr.Reader(['ch_sim', 'en'], gpu=False)
    elif engine == "rapidocr":
        rapidocr = __import__("rapidocr_onnxruntime")
        _OCR_READER = rapidocr.RapidOCR()
    return _OCR_READER


def _beijing_weekday() -> str:
    """返回北京时区当前星期（如 '周三'）"""
    beijing = timezone(timedelta(hours=8))
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[datetime.now(beijing).weekday()]


def image_to_text(image_path: str) -> str:
    """OCR 识别图片，返回原始文本字符串（按 Y 坐标行序）"""
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")

    ext = os.path.splitext(image_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {ext}，支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    reader = _get_ocr_reader()
    if reader is None:
        raise ImportError(
            "未安装 OCR 引擎。请安装:\n"
            "  pip install rapidocr_onnxruntime -i https://pypi.tuna.tsinghua.edu.cn/simple"
        )

    engine = _detect_ocr_engine()

    if engine == "easyocr":
        raw_results = reader.readtext(image_path)
        results = [(bbox, text, conf) for bbox, text, conf in raw_results
                   if conf >= OCR_CONFIDENCE_THRESH]
    elif engine == "rapidocr":
        raw_results, _ = reader(image_path)
        if not raw_results:
            results = []
        else:
            results = [(box, text, conf) for box, text, conf in raw_results
                       if conf >= OCR_CONFIDENCE_THRESH]
    else:
        raise RuntimeError(f"不支持的 OCR 引擎: {engine}")

    if not results:
        return ""

    # 按 Y 坐标行分组
    def _row_y(item):
        bbox = item[0]
        ys = [pt[1] for pt in bbox]
        return sum(ys) / len(ys)

    items_with_y = [(_row_y(item), item) for item in results]
    items_with_y.sort(key=lambda x: x[0])

    lines = []
    current_line = [items_with_y[0]]
    for i in range(1, len(items_with_y)):
        if items_with_y[i][0] - current_line[-1][0] <= LINE_GROUP_THRESHOLD:
            current_line.append(items_with_y[i])
        else:
            lines.append(current_line)
            current_line = [items_with_y[i]]
    if current_line:
        lines.append(current_line)

    # 每行内按 X 排序
    def _text_x(item):
        bbox = item[1][0]
        xs = [pt[0] for pt in bbox]
        return sum(xs) / len(xs)

    text_lines = []
    for line in lines:
        line.sort(key=_text_x)
        texts = [item[1][1] for item in line]
        text_lines.append(" ".join(texts))

    return "\n".join(text_lines)


def text_to_markdown(ocr_text: str) -> str:
    """原始 OCR 文本 → 结构化 Markdown"""
    if not ocr_text or not ocr_text.strip():
        return ""

    lines = ocr_text.strip().splitlines()
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = re.split(r'\s{2,}', line)
        if len(parts) >= 3:
            cleaned = " | ".join(p.strip() for p in parts)
            cleaned_lines.append(f"| {cleaned} |")
        else:
            cleaned_lines.append(line)

    return "\n\n".join(cleaned_lines) if len(cleaned_lines) <= 3 else "\n".join(cleaned_lines)


def build_pic_messages(markdown_text: str) -> list[dict]:
    """构建 Chat messages，使用图片版 system prompt"""
    today = _beijing_weekday()
    user_text = (
        f"今天是{today}，请分析以下文本中的足球比赛预测，"
        f"提取所有{today}的比赛结果。\n\n"
        f"{markdown_text}"
    )
    return [
        {"role": "system", "content": ai_config.get_system_prompt_pic()},
        {"role": "user", "content": user_text},
    ]


def extract_predictions_from_image(image_path: str) -> dict:
    """图片 → OCR → AI → 结构化结果"""
    raw_text = image_to_text(image_path)
    if not raw_text:
        return {
            "predictions": [],
            "raw": "",
            "warning": "图片未识别到文字",
        }

    md_text = text_to_markdown(raw_text)
    messages = build_pic_messages(md_text)
    response_text = ai_client.call_deepseek(messages)
    return ai_parser.parse_ai_result(response_text)
