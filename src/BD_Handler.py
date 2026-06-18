"""
BD（北单）模式数据处理模块
=========================
从 AI/test_bd_v2.py 提取的 BD 特有逻辑，不依赖 table_qt。

适用场景：北单文件按比赛组织（1文件=N场比赛），Excel 编号为纯数字或"北单+数字"。
"""
import os
import re


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
