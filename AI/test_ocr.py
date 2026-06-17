"""
OCR 图片比分预测提取 — 测试脚本
外部测试模块，不修改任何现有代码。
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from AI.ocr_extractor import (
    image_to_text,
    text_to_markdown,
    save_ocr_markdown,
    build_pic_messages,
    extract_from_image,
    SUPPORTED_EXTENSIONS,
)
from AI.ai_extractor import API_KEY

# 测试图片目录
TEST_IMG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "test_excel"
)


def test_ocr_only(image_path: str, verbose: bool = True):
    """仅测试 OCR 识别（不调 API）"""
    print(f"\n{'='*60}")
    print(f"图片: {os.path.basename(image_path)}")

    if not os.path.isfile(image_path):
        print(f"  文件不存在: {image_path}")
        return None, None

    # Step 1: OCR
    try:
        raw_text = image_to_text(image_path)
    except Exception as e:
        print(f"  OCR 识别失败: {e}")
        return None, None

    if not raw_text:
        print("  OCR 未识别到文字")
        return None, None

    if verbose:
        print(f"\n  --- OCR 原始文本 (前 800 字) ---")
        print(f"  {raw_text[:800]}")

    # Step 2: Markdown
    md_text = text_to_markdown(raw_text)
    if verbose:
        print(f"\n  --- Markdown 文本 (前 800 字) ---")
        print(f"  {md_text[:800]}")

    # 保存
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    md_path = save_ocr_markdown(md_text, image_name=image_name)
    print(f"\n  OCR Markdown 已保存: {md_path}")

    return raw_text, md_text


def test_full_pipeline(image_path: str, verbose: bool = True) -> dict | None:
    """完整流程：OCR + Deepseek API + 解析"""
    print(f"\n{'='*60}")
    print(f"完整流程测试: {os.path.basename(image_path)}")

    if not API_KEY:
        print("\n  未设置 DEEPSEEK_API_KEY，跳过 API 调用")
        return None

    # Step 1-2: OCR + Markdown
    try:
        raw_text = image_to_text(image_path)
    except Exception as e:
        print(f"  OCR 识别失败: {e}")
        return None

    if not raw_text:
        print("  OCR 未识别到文字")
        return None

    md_text = text_to_markdown(raw_text)
    if verbose:
        print(f"\n  OCR 文本长度: {len(raw_text)} 字符")
        print(f"  Markdown 文本长度: {len(md_text)} 字符")

    # 保存 Markdown
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    md_path = save_ocr_markdown(md_text, image_name=image_name)
    print(f"  OCR Markdown 已保存: {md_path}")

    # Step 3: Build messages
    messages = build_pic_messages(md_text)
    if verbose:
        print(f"\n  --- User Prompt (前 300 字) ---")
        print(f"  {messages[1]['content'][:300]}")

    # Step 4: Call API
    try:
        from AI.ai_extractor import call_deepseek
        print("\n  正在调用 Deepseek API...")
        response_text = call_deepseek(messages)
        print(f"\n  --- AI 原始响应 ---")
        print(f"  {response_text}")
    except Exception as e:
        print(f"\n  API 调用失败: {e}")
        return None

    # Step 5: Parse
    from AI.ai_extractor import parse_response
    result = parse_response(response_text)
    print(f"\n  --- 结构化结果 ---")
    for code, data in sorted(result.items()):
        wdl = " ".join(data["wdl"])
        scores = " ".join(data["scores"])
        print(f"  {code}  {wdl}  {scores}")

    return result


def test_ocr_detail(image_path: str):
    """OCR 详细信息：bbox + confidence"""
    print(f"\n{'='*60}")
    print(f"OCR 详细信息: {os.path.basename(image_path)}")

    try:
        from AI.ocr_extractor import _get_ocr_reader, _detect_ocr_engine, OCR_CONFIDENCE_THRESH
        reader = _get_ocr_reader()
        engine = _detect_ocr_engine()
        print(f"  OCR 引擎: {engine}")
        print(f"  置信度阈值: {OCR_CONFIDENCE_THRESH}")

        if engine == "easyocr":
            raw_results = reader.readtext(image_path)
        elif engine == "rapidocr":
            raw_results, _ = reader(image_path)
            if raw_results is None:
                raw_results = []
        else:
            raw_results = []

        print(f"  识别到 {len(raw_results)} 个文本块\n")

        for i, item in enumerate(raw_results):
            if engine == "easyocr":
                bbox, text, conf = item
            else:
                bbox, text, conf = item
            y_avg = sum(pt[1] for pt in bbox) / 4
            x_avg = sum(pt[0] for pt in bbox) / 4
            print(f"  [{i:2d}] Y={y_avg:6.1f} X={x_avg:6.1f}  "
                  f"[{bbox[0][0]:.0f},{bbox[0][1]:.0f}]"
                  f"  conf={conf:.2f}  '{text}'")
    except Exception as e:
        print(f"  OCR 详情获取失败: {e}")


def main():
    print("OCR 图片比分预测提取 — 测试")
    print(f"API Key 已设置: {'YES' if API_KEY else 'NO (OCR only)'}")
    print(f"OCR 引擎: ", end="")

    from AI.ocr_extractor import _detect_ocr_engine
    engine = _detect_ocr_engine()
    print(f"{engine if engine else '未安装'}")

    if not os.path.isdir(TEST_IMG_DIR):
        print(f"测试目录不存在: {TEST_IMG_DIR}")
        return

    # 扫描图片文件
    image_files = []
    for ext in SUPPORTED_EXTENSIONS:
        image_files.extend(Path(TEST_IMG_DIR).glob(f"*{ext}"))
        image_files.extend(Path(TEST_IMG_DIR).glob(f"*{ext.upper()}"))
    image_files = sorted(set(image_files))

    print(f"找到 {len(image_files)} 个图片文件")

    if not image_files:
        print("未找到测试图片")
        return

    # 默认测试第一个图片
    test_file = str(image_files[0])
    print(f"\n测试图片: {os.path.basename(test_file)}")

    # 1. OCR 详细信息
    test_ocr_detail(test_file)

    # 2. OCR only
    raw_text, md_text = test_ocr_only(test_file, verbose=True)

    # 3. 完整流程（如果有 API key）
    if API_KEY and raw_text:
        test_full_pipeline(test_file, verbose=True)


if __name__ == "__main__":
    main()
