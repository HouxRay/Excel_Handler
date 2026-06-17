"""
OCR 图片文字识别提取器
独立模块，不依赖项目其他代码。Image -> OCR -> Markdown -> Deepseek API -> 结构化输出。
外部测试模块，不修改任何现有代码。
"""
import importlib
import importlib.util
import os
import re
import sys
from datetime import datetime, timezone, timedelta

# --- 配置 ---
SYSTEM_PROMPT_PIC = """# Role
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

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp'}
OCR_CONFIDENCE_THRESH = 0.3          # 置信度阈值，低于此值忽略
LINE_GROUP_THRESHOLD = 15            # Y坐标行分组阈值（像素）

# --- OCR 引擎检测与缓存 ---
_OCR_ENGINE = None
_OCR_READER = None


def _detect_ocr_engine() -> str | None:
    """自动检测可用的 OCR 引擎，优先级: rapidocr > easyocr

    RapidOCR 模型内置在包中无需下载，优先使用。
    """
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


def _get_ocr_reader() -> object | None:
    """惰性加载 OCR reader（模块级缓存复用）"""
    global _OCR_READER
    if _OCR_READER is not None:
        return _OCR_READER

    engine = _detect_ocr_engine()
    if engine == "easyocr":
        easyocr = importlib.import_module("easyocr")
        _OCR_READER = easyocr.Reader(['ch_sim', 'en'], gpu=False)
    elif engine == "rapidocr":
        rapidocr = importlib.import_module("rapidocr_onnxruntime")
        _OCR_READER = rapidocr.RapidOCR()
    return _OCR_READER


def _beijing_weekday() -> str:
    """返回北京时区当前星期（如 '周三'）"""
    beijing = timezone(timedelta(hours=8))
    names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return names[datetime.now(beijing).weekday()]


def image_to_text(image_path: str) -> str:
    """OCR 识别图片，返回原始文本字符串

    使用 RapidOCR / EasyOCR 读取图片文字，按 Y 坐标分组排列保留行序。
    """
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
        # 过滤低置信度结果
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

    # --- 按 Y 坐标行分组 ---
    # 取每个 bbox 左上角和左下角的 Y 均值作为行位置
    def _row_y(item):
        bbox = item[0]
        ys = [pt[1] for pt in bbox]
        return sum(ys) / len(ys)

    items_with_y = [(_row_y(item), item) for item in results]
    items_with_y.sort(key=lambda x: x[0])  # 按 Y 排序

    # 分组：Y 差在阈值内视为同一行
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
        # 检测是否为表格行（含多个空格分隔的列）
        parts = re.split(r'\s{2,}', line)
        if len(parts) >= 3:
            # 表格行 -> Markdown 表格行
            cleaned = " | ".join(p.strip() for p in parts)
            cleaned_lines.append(f"| {cleaned} |")
        else:
            cleaned_lines.append(line)

    return "\n\n".join(cleaned_lines) if len(cleaned_lines) <= 3 else "\n".join(cleaned_lines)


def save_ocr_markdown(markdown_text: str, output_dir: str | None = None,
                      image_name: str = "ocr_result") -> str:
    """保存 OCR 结果为 .md 文件"""
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{image_name}_ocr_{ts}.md"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# OCR 识别结果\n\n")
        f.write(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(markdown_text)

    return filepath


def build_pic_messages(markdown_text: str) -> list[dict]:
    """构建 Chat messages，使用 Pic.md 的 system prompt"""
    today = _beijing_weekday()
    user_text = (
        f"今天是{today}，请分析以下文本中的足球比赛预测，"
        f"提取所有{today}的比赛结果。\n\n"
        f"{markdown_text}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT_PIC},
        {"role": "user", "content": user_text},
    ]


def extract_from_image(image_path: str, save_markdown: bool = True) -> dict:
    """全流程入口：图片 → 结构化比分预测

    Args:
        image_path: 图片文件路径
        save_markdown: 是否保存 OCR Markdown 到文件

    Returns:
        {code: {"wdl": [...], "scores": [...]}}
    """
    # Step 1-2: OCR + Markdown
    raw_text = image_to_text(image_path)
    if not raw_text:
        return {}

    md_text = text_to_markdown(raw_text)

    # Step 2b: 保存 Markdown
    if save_markdown:
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        md_path = save_ocr_markdown(md_text, image_name=image_name)
        print(f"  OCR Markdown 已保存: {md_path}")

    # Step 3: 构建 messages
    messages = build_pic_messages(md_text)

    # Step 4-5: API 调用 + 解析
    from AI.ai_extractor import call_deepseek, parse_response

    response_text = call_deepseek(messages)
    return parse_response(response_text)


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="OCR 图片文字识别提取器")
    parser.add_argument("image", nargs="?", default=None, help="图片文件路径")
    parser.add_argument("--ocr-only", action="store_true", help="仅测试 OCR，不调用 API")
    parser.add_argument("--verbose", action="store_true", help="输出详细信息")
    args = parser.parse_args()

    image_path = args.image
    if image_path is None:
        image_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "test_excel", "image.png"
        )

    print(f"OCR 图片文字识别提取")
    print(f"图片: {image_path}")

    if not os.path.isfile(image_path):
        print(f"错误: 文件不存在: {image_path}")
        sys.exit(1)

    # OCR only
    print(f"\n{'='*60}")
    print("Step 1-2: OCR 识别 + Markdown 转换")
    raw_text = image_to_text(image_path)
    print(f"\n  --- OCR 原始文本 ---")
    print(f"  {raw_text[:1500] if args.verbose else raw_text[:500]}")

    md_text = text_to_markdown(raw_text)
    print(f"\n  --- Markdown 文本 ---")
    print(f"  {md_text[:1500] if args.verbose else md_text[:500]}")

    # 保存 Markdown
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    md_path = save_ocr_markdown(md_text, image_name=image_name)
    print(f"\n  OCR Markdown 已保存: {md_path}")

    if args.ocr_only:
        return

    # Full pipeline
    print(f"\n{'='*60}")
    print("Step 3-5: Deepseek API 调用 + 解析")

    from AI.ai_extractor import API_KEY, call_deepseek, parse_response
    if not API_KEY:
        print("\n  未设置 DEEPSEEK_API_KEY，跳过 API 调用")
        return

    messages = build_pic_messages(md_text)
    if args.verbose:
        print(f"\n  --- User Prompt (前 300 字) ---")
        print(f"  {messages[1]['content'][:300]}")

    try:
        print("\n  正在调用 Deepseek API...")
        response_text = call_deepseek(messages)
        print(f"\n  --- AI 原始响应 ---")
        print(f"  {response_text}")
    except Exception as e:
        print(f"\n  API 调用失败: {e}")
        return

    result = parse_response(response_text)
    print(f"\n  --- 结构化结果 ---")
    for code, data in sorted(result.items()):
        wdl = " ".join(data["wdl"])
        scores = " ".join(data["scores"])
        print(f"  {code}  {wdl}  {scores}")

    return result


if __name__ == "__main__":
    main()
