"""
AI 比分预测提取 — 测试脚本
遍历 test_excel 中的 HTML 文件，调用 AI 提取预测结果
"""
import os
import sys
import json
from pathlib import Path

# 确保可以导入 ai 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from AI.ai_extractor import (
    html_to_markdown,
    build_messages,
    call_deepseek,
    parse_response,
    extract_predictions,
    API_KEY,
)

# 测试目录
TEST_HTML_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "test_excel", "2026-05-12-jc", "2026-05-12-jc"
)


def test_single_file(html_path: str, verbose: bool = True):
    """测试单个 HTML 文件的完整流程"""
    print(f"\n{'='*60}")
    print(f"文件: {os.path.basename(html_path)}")

    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"  读取失败: {e}")
        return None

    # Step 1: HTML → Markdown
    markdown = html_to_markdown(html_content)
    if verbose:
        print(f"\n  --- Markdown (前 500 字) ---")
        print(f"  {markdown[:900]}")

    # Step 2: Build messages
    messages = build_messages(markdown)
    if verbose:
        print(f"\n  --- User Prompt (前 300 字) ---")
        print(f"  {messages[1]['content'][:300]}")

    # Step 3: Call API
    if not API_KEY:
        print("\n  ⚠️ 未设置 DEEPSEEK_API_KEY，跳过 API 调用")
        return None

    try:
        print("\n  正在调用 Deepseek API...")
        response_text = call_deepseek(messages)
        print(f"\n  --- AI 原始响应 ---")
        print(f"  {response_text}")
    except Exception as e:
        print(f"\n  ❌ API 调用失败: {e}")
        return None

    # Step 4: Parse
    result = parse_response(response_text)
    print(f"\n  --- 结构化结果 ---")
    for code, data in sorted(result.items()):
        wdl = " ".join(data["wdl"])
        scores = " ".join(data["scores"])
        print(f"  {code}  {wdl}  {scores}")

    return result


def test_markdown_only(html_path: str):
    """仅测试 HTML→Markdown 转换（无需 API）"""
    print(f"\n文件: {os.path.basename(html_path)}")
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    markdown = html_to_markdown(html_content)
    print(f"Markdown 长度: {len(markdown)} 字符")
    print(markdown[:1000])
    print("...")


def main():
    print("AI 比分预测提取 — 测试")
    print(f"API Key 已设置: {'✅' if API_KEY else '❌ (仅测试转换)'}")

    if not os.path.isdir(TEST_HTML_DIR):
        print(f"测试目录不存在: {TEST_HTML_DIR}")
        return

    html_files = sorted(Path(TEST_HTML_DIR).glob("*.html"))
    print(f"找到 {len(html_files)} 个 HTML 文件")

    # 选择一个文件测试完整流程
    # test_file = os.path.join(TEST_HTML_DIR, "八神竞猜.html")
    test_file = r"D:\Excel_Hander\excel\2026-05-22-jc\2026-05-22-jc\八神竞猜.html"
    if os.path.exists(test_file):
        result = test_single_file(test_file)

    # # 可选：测试汇总表
    # summary = os.path.join(TEST_HTML_DIR, "A数量.html")
    # if os.path.exists(summary):
    #     print(f"\n{'='*60}")
    #     print("测试汇总表 (A数量.html) — 仅转换")
    #     test_markdown_only(summary)


if __name__ == "__main__":
    main()
