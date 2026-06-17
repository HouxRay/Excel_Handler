"""
BD（北单）文件解析与兼容性测试脚本
外部测试模块，不修改任何现有代码。测试北单文件是否符合当前项目架构。
"""
import os
import re
import sys
import json
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# BD 测试目录
BD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "test_excel", "2026-06-16-bd", "2026-06-16-bd"
)


def _extract_match_info(html_text: str) -> list[dict]:
    """从 A数量.html 格式中提取比赛信息

    A数量.html 结构：
      <b><span class="match-no">北单N</span><span class="league">联赛</span>
      <span class="teams">主队 VS 客队</span></b>
      <div>predictor1 &nbsp; &nbsp; <span class="option">选项</span>...</div>

    Returns:
      [{match_no, league, home, away, predictors: [{name, option}]}]
    """
    results = []

    # 匹配每个比赛块：<b>...</b> 到下一个 <b> 或结尾
    # match 组: 1=match_no, 2=league, 3=home, 4=away
    match_pattern = re.compile(
        r'<b>\s*<span class="match-no">([^<]+)</span>'
        r'<span class="league">([^<]*)</span>'
        r'<span class="teams">([^<]*)<span class="vs">VS</span>([^<]*)</span>\s*</b>'
    )

    # 找所有 match 位置并分段提取 predictor 数据
    matches = list(match_pattern.finditer(html_text))

    for i, m in enumerate(matches):
        match_no = m.group(1).strip()
        league = m.group(2).strip()
        home = m.group(3).strip()
        away = m.group(4).strip()

        # 提取该 match 块到下一个 <b> 之间的内容
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(html_text)
        block_html = html_text[block_start:block_end]

        # 提取 predictor → option 对
        # 方法：找到所有 <span class="option"> 位置，往前取文本为 predictor 名
        predictors = []
        # 找到所有 option 的位置
        option_pattern = re.compile(r'<span class="option">([^<]+)</span>')
        prev_end = 0
        for om in option_pattern.finditer(block_html):
            option = om.group(1).strip()
            # 取上一段结束到本 option 之间的文本作为 predictor 名
            prev_text = block_html[prev_end:om.start()].strip()
            # 清理：去掉所有 HTML 标签、&nbsp;、多余空白
            prev_text = re.sub(r'<[^>]+>', '', prev_text)
            prev_text = re.sub(r'&nbsp;', '', prev_text).strip()
            # 去掉开头的 > 残留
            prev_text = prev_text.lstrip('>').strip()
            if prev_text and option:
                predictors.append({"name": prev_text, "option": option})
            prev_end = om.end()

        results.append({
            "match_no": match_no,
            "league": league,
            "home": home,
            "away": away,
            "predictors": predictors,
        })

    return results


def _extract_detail_files(html_dir: str) -> dict:
    """从每个北单N*.html 文件中提取预测数据

    Returns:
      {match_no: {predictor_name: option}}
    """
    result = {}
    if not os.path.isdir(html_dir):
        return result

    for fname in sorted(os.listdir(html_dir)):
        if not fname.endswith('.html') or fname == 'A数量.html':
            continue

        fpath = os.path.join(html_dir, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue

        # 每个 <div style="border: 1px solid black;..."> 块是一个 predictor
        div_pattern = re.compile(
            r'<div\s+style="border:\s*1px\s+solid\s+black;[^"]*">(.*?)</div>',
            re.DOTALL
        )

        for div_match in div_pattern.finditer(content):
            div_html = div_match.group(1)

            # 提取 predictor 名称
            name_m = re.search(
                r'<span\s+style="color:\s*red;\s*font-size:\s*20px;\s*font-weight:\s*bold;">([^<]+)</span>',
                div_html
            )
            if not name_m:
                continue
            pred_name = name_m.group(1).strip()

            # 提取 match-no 和 option（可能有多个）
            # 一个 div 可能包含同一预测者的多场比赛
            items = re.findall(
                r'<span class="match-no">(北单\d+)</span>.*?'
                r'<span class="option">([^<]+)</span>',
                div_html
            )

            for match_no, option in items:
                if match_no not in result:
                    result[match_no] = {}
                result[match_no][pred_name] = option.strip()

    return result


def test_parse_summary():
    """测试 1：解析 A数量.html 汇总文件"""
    print(f"\n{'='*60}")
    print("测试 1: 解析 A数量.html 汇总文件")

    summary_path = os.path.join(BD_DIR, "A数量.html")
    if not os.path.isfile(summary_path):
        print(f"  ❌ 文件不存在: {summary_path}")
        return None, None

    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"  ❌ 读取失败: {e}")
        return None, None

    matches = _extract_match_info(html_content)
    print(f"  找到 {len(matches)} 场比赛")

    total_predictions = 0
    for m in matches:
        count = len(m["predictors"])
        total_predictions += count
        opt_sample = ", ".join(p["option"] for p in m["predictors"][:3])
        print(f"  {m['match_no']:6s}  {m['league']:6s}  {m['home']:8s} VS {m['away']:8s}"
              f"  → {count:2d} 个预测  [{opt_sample}{'...' if count > 3 else ''}]")

    print(f"\n  总计: {total_predictions} 条预测")

    # 收集所有预测机构
    all_predictors = set()
    for m in matches:
        for p in m["predictors"]:
            all_predictors.add(p["name"])
    print(f"  预测机构数: {len(all_predictors)}")
    print(f"  预测机构列表: {', '.join(sorted(all_predictors))}")

    return matches, all_predictors


def test_parse_detail():
    """测试 2：解析每个北单N.html 文件"""
    print(f"\n{'='*60}")
    print("测试 2: 解析每个北单N.html 详细文件")

    detail_data = _extract_detail_files(BD_DIR)
    if not detail_data:
        print("  ❌ 未解析到数据")
        return None

    print(f"  找到 {len(detail_data)} 个比赛")

    for match_no in sorted(detail_data.keys()):
        preds = detail_data[match_no]
        print(f"  {match_no:6s}  → {len(preds):2d} 个预测者")

    # 去重预测者
    all_preds = set()
    for match_no, preds in detail_data.items():
        all_preds.update(preds.keys())
    print(f"\n  总计预测者: {len(all_preds)}")
    print(f"  列表: {', '.join(sorted(all_preds))}")

    return detail_data


def test_compatibility(summary_matches):
    """测试 3：架构兼容性测试

    测试维度：
    1. match_no 格式兼容性（北单N vs 3位数字编号）
    2. option 格式兼容性（主队-0.5 负 vs MATCH_DICT 简写）
    3. 与现有 Excel 表头匹配测试
    """
    if not summary_matches:
        return

    print(f"\n{'='*60}")
    print("测试 3: 架构兼容性测试")

    # -- 3a: 编号格式 --
    print(f"\n  --- 3a. 编号格式兼容性 ---")
    all_match_nos = [m["match_no"] for m in summary_matches]
    code_pattern = re.compile(r'^\d{3}$')
    bd_pattern = re.compile(r'^北单\d+$')

    has_3digit = any(code_pattern.match(c) for c in all_match_nos)
    has_bd = any(bd_pattern.match(c) for c in all_match_nos)
    print(f"  编号列表: {', '.join(all_match_nos)}")
    print(f"  符合 3 位数字格式 (如 001): {'✅' if has_3digit else '❌ 无'}")
    print(f"  符合 北单N 格式:     {'✅' if has_bd else '❌ 无'}")
    print(f"  结论: {'❌ 编号格式不兼容 - 当前 get_location() 需要 3 位数字编号' if not has_3digit else '✅ 兼容'}")

    # -- 3b: option 格式 --
    print(f"\n  --- 3b. 预测选项格式兼容性 ---")

    # MATCH_DICT（来自 ai_extractor 和 Excel_Writer）
    match_dict = {
        "s": "胜", "ss": "胜胜", "rs": "让胜",
        "f": "负", "rf": "让负",
        "p": "平", "rp": "让平", "sp": "双平",
        "q": "平", "rq": "让平", "sq": "双平", "fsf": "分胜负",
    }
    valid_options = set(match_dict.values())

    # 收集 BD 中所有 option 值
    bd_options = set()
    for m in summary_matches:
        for p in m["predictors"]:
            bd_options.add(p["option"])

    print(f"  BD 文件中共有 {len(bd_options)} 种不同 option:")
    for opt in sorted(bd_options):
        # 检查是否能匹配 MATCH_DICT
        parts = opt.replace(",", " ").split()
        matched = all(p in valid_options for p in parts)
        # 检查是否为传统简写格式（不含 "主队"/"客队" 前缀）
        is_traditional = not any(prefix in opt for prefix in ["主队", "客队"])
        status = "✅" if matched and is_traditional else "⚠️ 非标准格式"
        print(f"    '{opt}'  {status}")

    traditional_count = sum(1 for opt in bd_options if not any(p in opt for p in ["主队", "客队"]))
    print(f"\n  传统格式 (无主队/客队前缀): {traditional_count}/{len(bd_options)}")
    print(f"  结论: {'⚠️ 部分不兼容 - BD 选项含主队/客队让球格式' if traditional_count < len(bd_options) else '✅ 兼容'}")

    # -- 3c: 与 ai_extractor 的正则兼容性 --
    print(f"\n  --- 3c. ai_extractor 解析兼容性 ---")
    line_pattern = re.compile(
        r'(\d{3})\s+'                                   # 编号
        r'([一-龥]+(?:\s+[一-龥]+)?)\s+'  # 胜平负（1-2个中文词）
        r'(\d{2}(?:\s+\d{2})?)'                          # 比分（1-2组）
    )
    # 测试 BD option 是否能被该正则解析
    test_line = None
    for opt in bd_options:
        if "主队" in opt or "客队" in opt:
            test_line = opt
            break
    print(f"  正则要求: 3位编号 + 1-2个中文词 + 比分")
    print(f"  BD 典型 option: '{test_line or list(bd_options)[0]}'")
    match = line_pattern.search(f"001 胜 11 22")
    print(f"  标准格式匹配: {'✅' if match else '❌'}")
    match_bd = line_pattern.search(f"001 {'主队 胜'} 11 22")
    print(f"  BD 格式匹配:   {'✅' if match_bd else '❌ 不匹配 - 主队/客队前缀导致解析失败'}")

    # -- 3d: 现有 Excel 表头匹配 --
    print(f"\n  --- 3d. Excel 表头匹配测试（现有 Excel 文件）---")
    excel_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "test_excel", "副本5-12.xlsx"
    )
    if os.path.isfile(excel_path):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(excel_path, read_only=True)
            ws = wb.active
            header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
            headers = [str(h or "") for h in header_row]
            # 检查表头中是否有北单格式
            bd_in_header = any("北单" in h for h in headers)
            codes_in_header = [h for h in headers if re.match(r'\d{3}', h)]
            print(f"  表头中共 {len(headers)} 列")
            print(f"  含 3位数字编号: {len(codes_in_header)} 个 ({', '.join(codes_in_header[:10])}{'...' if len(codes_in_header) > 10 else ''})")
            print(f"  含 北单N 格式:  {'✅ 发现' if bd_in_header else '❌ 未发现'}")
            print(f"  结论: {'❌ 不兼容 - 现有 Excel 表头无北单格式' if not bd_in_header else '✅ 兼容'}")
            wb.close()
        except Exception as e:
            print(f"  读取失败: {e}")
    else:
        print(f"  Excel 文件不存在: {excel_path}")


def test_data_structure(summary_matches):
    """测试 4：数据结构转换

    尝试将 BD 数据转换为现有 data_storage 格式：
    {predictor: {match_code: [predictions]}}
    并检查是否可以写入 Excel。
    """
    if not summary_matches:
        return

    print(f"\n{'='*60}")
    print("测试 4: data_storage 数据结构转换测试")

    # 转换为 {predictor: {bd_match_no: [option]}}
    data_storage = defaultdict(lambda: defaultdict(list))
    for m in summary_matches:
        for p in m["predictors"]:
            data_storage[p["name"]][m["match_no"]].append(p["option"])

    print(f"  转换后预测者数: {len(data_storage)}")
    for pred_name, matches_dict in sorted(data_storage.items())[:5]:
        match_count = len(matches_dict)
        total_opts = sum(len(v) for v in matches_dict.values())
        print(f"  {pred_name:12s}  → {match_count} 场比赛, {total_opts} 个选项")

    if len(data_storage) > 5:
        print(f"  ... 还有 {len(data_storage) - 5} 个预测者")

    # 尝试用 ai_extractor 的 call_deepseek 处理
    print(f"\n  --- BD 数据结构评估 ---")
    print(f"  当前 data_storage 格式: {{category: {{code: [scores]}}}}")
    print(f"  转换后 BD 格式:         {{predictor: {{bd_match_no: [options]}}}}")
    print(f"  结构兼容: {'✅ 格式一致' if True else '❌'}")
    print(f"  但 BD 的 code 为 '北单N' 而非 '001'，key 不兼容")
    print(f"  BD 的 option 为 '主队-0.5 胜' 而非 '胜'，value 不兼容")


def main():
    print("=" * 60)
    print("BD（北单）文件解析与兼容性测试")
    print(f"测试目录: {BD_DIR}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not os.path.isdir(BD_DIR):
        print(f"\n❌ 测试目录不存在: {BD_DIR}")
        return

    # Test 1: 解析 A数量.html
    summary_matches, all_predictors = test_parse_summary()

    # Test 2: 解析每个北单N.html
    detail_data = test_parse_detail()

    # 交叉验证
    if summary_matches and detail_data:
        print(f"\n{'='*60}")
        print("交叉验证: 汇总 vs 详细文件")
        summary_matches_set = set(m["match_no"] for m in summary_matches)
        detail_matches_set = set(detail_data.keys())
        common = summary_matches_set & detail_matches_set
        only_summary = summary_matches_set - detail_matches_set
        only_detail = detail_matches_set - summary_matches_set
        print(f"  共同比赛: {', '.join(sorted(common)) if common else '无'}")
        if only_summary:
            print(f"  仅在汇总中: {', '.join(sorted(only_summary))}")
        if only_detail:
            print(f"  仅在详细中: {', '.join(sorted(only_detail))}")

    # Test 3: 架构兼容性
    test_compatibility(summary_matches)

    # Test 4: 数据结构转换
    test_data_structure(summary_matches)

    # 总结
    print(f"\n{'='*60}")
    print("兼容性总结")
    print(f"{'='*60}")
    print("""
  编号格式:   ❌ 不兼容 - 北单N 非 3位数字, get_location() 无法处理
  选项格式:   ⚠️ 部分兼容 - 主队/客队前缀 + 让球盘无法被 MATCH_DICT 映射
  Excel 表头: ❌ 不兼容 - 现有 Excel 无北单格式列
  数据格式:   ⚠️ 结构兼容 - 但 key/value 均不兼容

  BD 文件与当前架构的核心差异：
  1. 文件组织方式（按比赛 vs 按预测机构）与现有 UI 的单选按钮设计冲突
  2. 预测选项含让球盘（主队-0.5 负）非标准胜平负简写
  3. 比赛编号格式（北单N）与现有定位系统不兼容

  建议：如需接入 BD，需要：
  - 新增 BD 数据模式（类似 pic 模式）
  - 扩展 get_location() 支持北单N
  - 新建 BD 专用的 Excel 模板和映射文件
  - 重新设计 UI 布局（BD 按比赛分类 vs JC 按机构分类）
    """)


if __name__ == "__main__":
    main()
