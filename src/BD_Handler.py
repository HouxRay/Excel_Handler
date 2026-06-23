"""
BD（北单）模式数据处理模块
=========================
从 AI/test_bd_v2.py 提取的 BD 特有逻辑，不依赖 table_qt。

适用场景：北单文件按比赛组织（1文件=N场比赛），Excel 编号为纯数字或"北单+数字"。
"""
import os
import re
import glob
from collections import Counter, defaultdict
from openpyxl import load_workbook
from src.Excel_Writer import ExcelWriter
from src.mapping_manager import apply_keyboard_mappings


def parse_bd_summary(html_path: str) -> list[dict]:
    """解析 A数量.html — 每场比赛一个 <b> 块，内含多机构预测。

    Returns: [{match_no, league, home, away, predictors: [{name, option}]}]
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    match_hdr = re.compile(
        r'<b>\s*<span class="match-no">([^<]+)</span>'
        r'<span class="league">([^<]*)</span>'
        r'<span class="teams">([^<]*)<span class="vs">VS</span>([^<]*)</span>\s*</b>'
    )
    matches = list(match_hdr.finditer(html))
    results = []

    for i, m in enumerate(matches):
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        block_html = html[block_start:block_end]

        option_pat = re.compile(r'<span class="option">([^<]+)</span>')
        predictors = []
        prev_end = 0
        for om in option_pat.finditer(block_html):
            option = om.group(1).strip()
            prev_text = block_html[prev_end:om.start()]
            prev_text = re.sub(r'<[^>]+>', '', prev_text)
            prev_text = re.sub(r'&nbsp;', '', prev_text).strip().lstrip('>').strip()
            if prev_text and option:
                predictors.append({"name": prev_text, "option": option})
            prev_end = om.end()

        results.append({
            "match_no": m.group(1).strip(),
            "league":   m.group(2).strip(),
            "home":     m.group(3).strip(),
            "away":     m.group(4).strip(),
            "predictors": predictors,
        })
    return results


def parse_bd_detail(bd_html_dir: str) -> dict:
    """从北单N.html 中用正则提取"比分预测：2-1,3-1"形式的比分。

    Returns: {code_num: [[a,b], [a,b], ...]}  每个比分已 zfill(2)
    """
    result = {}
    if not os.path.isdir(bd_html_dir):
        return result

    for fname in sorted(os.listdir(bd_html_dir)):
        if not fname.endswith('.html') or fname == 'A数量.html':
            continue
        m = re.match(r'北单(\d+)', fname)
        if not m:
            continue
        code_num = m.group(1)

        with open(os.path.join(bd_html_dir, fname), 'r', encoding='utf-8') as f:
            html = f.read()

        score_pat = re.compile(r'(\d+)[-:](\d+)')
        matches = score_pat.findall(html)
        if matches:
            seen = set()
            scores = []
            for a, b in matches:
                key = f"{a}{b}"
                if key not in seen:
                    seen.add(key)
                    scores.append([a.zfill(2), b.zfill(2)])
            result[code_num] = scores
    return result


def normalize(code: str) -> str:
    """北单4 → 4"""
    return code.replace("北单", "").strip()


def find_bd_columns(ws) -> dict:
    """扫描 Excel row 1，用正则 ^(?:北单)?(\d+)$ 匹配纯数字或北单+数字。

    4 列一组：[code][team1][team2][empty]

    Returns: {code_num: {"start_col": int, "teams": [team1, team2]}}
    """
    code_pattern = re.compile(r'^(?:北单)?(\d+)$')
    raw = {}
    for cell in ws[1]:
        if cell.value is None:
            continue
        m = code_pattern.match(str(cell.value).strip())
        if m:
            raw[m.group(1)] = cell.column

    result = {}
    for code_num, start_col in raw.items():
        teams = ["", ""]
        if start_col + 1 <= ws.max_column:
            v = ws.cell(row=1, column=start_col + 1).value
            teams[0] = str(v).strip() if v else ""
        if start_col + 2 <= ws.max_column:
            v = ws.cell(row=1, column=start_col + 2).value
            teams[1] = str(v).strip() if v else ""
        result[code_num] = {"start_col": start_col, "teams": teams}
    return result


def load_bd_config(excel_path, html_dir, sheet_name, bd_json_restore, logger):
    """
    加载北单模式配置 — 从 Excel 和 HTML 目录扫描。

    Returns: (bd_categories, bd_data_storage)
        bd_categories: [label, ...]
        bd_data_storage: {label: {code, home, away, scores, html_file}}
    """
    bd_categories = []
    bd_data_storage = {}
    try:
        if not excel_path or not os.path.exists(excel_path):
            return bd_categories, bd_data_storage

        wb = load_workbook(excel_path, read_only=True)
        if sheet_name and sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            ws = wb.active
        col_map = find_bd_columns(ws)
        if not col_map:
            wb.close()
            logger.warning(f"BD Excel 未找到比赛编号 (row1 cols 2-{ws.max_column})")
            return bd_categories, bd_data_storage

        # 2. 递归扫描 BD HTML 目录
        available = {}
        if html_dir and os.path.isdir(html_dir):
            for fpath in glob.glob(os.path.join(html_dir, '**', '*.html'), recursive=True):
                fname = os.path.basename(fpath)
                if fname == 'A数量.html':
                    continue
                m = re.search(r'北单(\d+)', fname)
                if m:
                    num = m.group(1)
                    if num not in available:
                        available[num] = fpath

        # 3. 按 Excel 列顺序构建列表
        sorted_codes = sorted(col_map.keys(),
                              key=lambda x: int(x) if x.isdigit() else 999)
        for code_str in sorted_codes:
            info = col_map[code_str]
            home, away = info["teams"]
            label = f"北单{code_str} {home} VS {away}" if home else f"北单{code_str}"

            match_file = None
            code_int = int(code_str)
            for fnum, fpath in available.items():
                if int(fnum) == code_int:
                    match_file = fpath
                    break

            bd_categories.append(label)
            bd_data_storage[label] = {
                "code": code_str,
                "home": home,
                "away": away,
                "scores": [],
                "html_file": match_file,
            }
        wb.close()

        # 4. 从 JSON 恢复 BD 数据
        if bd_json_restore:
            restored = 0
            for label, info in bd_json_restore.items():
                if label in bd_data_storage:
                    bd_data_storage[label]["scores"] = info.get("scores", [])
                    restored += 1
            if restored:
                logger.info(f"BD 从 JSON 恢复 {restored} 场比赛数据")

        logger.info(f"BD 加载: {len(bd_categories)} 个比赛"
                    f" ({sum(1 for v in bd_data_storage.values() if v['html_file'])} 个匹配文件)")
    except Exception as e:
        logger.exception("BD 配置加载失败")

    return bd_categories, bd_data_storage


def export_bd_data(bd_info, excel_path, sheet, _bd_export_rows, logger):
    """
    BD 模式导出 — 纵向追加写入，覆盖已有导出行。
    Returns: (success, message)
    """
    scores = bd_info.get("scores", [])
    code = bd_info.get("code", "")

    writer = ExcelWriter(excel_path, sheet)
    col_map = find_bd_columns(writer.ws)
    if code not in col_map:
        return False, f"Excel 中未找到编号 {code} 的列"

    sc = col_map[code]["start_col"]

    prev_info = _bd_export_rows.get(code)
    if prev_info is not None:
        start_row, prev_count = prev_info
        row = start_row
        for r in range(row, row + prev_count):
            for c in range(4):
                writer.ws.cell(row=r, column=sc + c).value = None
    else:
        start_row = 2
        while start_row <= writer.ws.max_row:
            if writer.ws.cell(row=start_row, column=sc).value in (None, ""):
                break
            start_row += 1
        row = start_row

    for score_set in scores:
        normalized = [apply_keyboard_mappings(str(s)) for s in score_set[:4]]
        writer.batch_write_list(row, sc, normalized)
        row += 1

    writer.save()
    _bd_export_rows[code] = (start_row, len(scores))
    logger.info(f"BD 导出完成: {len(scores)} 行")
    return True, f"BD 导出完成: {len(scores)} 行"


def sort_bd_data(bd_data_storage, excel_path, sheet, logger):
    """
    BD 排序 — 统计比分频率，写入 Excel row 84。
    Returns: dict_counter or None
    """
    stats = defaultdict(Counter)
    skipped_count = 0
    for name, bd_info in bd_data_storage.items():
        for score_set in bd_info.get("scores", []):
            if not any(str(v).strip() for v in score_set):
                continue
            for value in score_set:
                value = str(value).strip()
                if not re.fullmatch(r'\d{2}', value):
                    if value:
                        skipped_count += 1
                    continue
                try:
                    iv = int(value)
                    if iv <= 50:
                        stats[bd_info["code"]][value] += 1
                    else:
                        skipped_count += 1
                except ValueError:
                    skipped_count += 1

    if skipped_count:
        logger.warning(f"BD 排序跳过 {skipped_count} 个无效或非比分值")

    dict_counter = {number: dict(counts.most_common()) for number, counts in stats.items()}

    writer = ExcelWriter(excel_path, sheet)
    col_map = find_bd_columns(writer.ws)
    for code_num, info in col_map.items():
        contents = dict_counter.get(code_num, {})
        if contents:
            sc = info["start_col"]
            writer.batch_write_cell(83, sc, f"BD{code_num}统计")
            writer.batch_write_dict(84, sc, contents)

    writer.save()
    logger.info("BD 排序完成")
    return dict_counter


def build_bd_data(parsed_matches: list[dict], detail_scores: dict) -> dict:
    """将解析结果转为 BD data_storage。

    Returns:
        {code_num: {
            "league": str, "home": str, "away": str,
            "scores": [[s1,s2], [s1,s2], ...]
        }}
    """
    bd_data = {}
    for m in parsed_matches:
        key = normalize(m["match_no"])
        bd_data[key] = {
            "league": m["league"],
            "home":   m["home"],
            "away":   m["away"],
            "scores": [],
        }
    for code, scores in detail_scores.items():
        if code in bd_data:
            bd_data[code]["scores"] = scores
    return bd_data
