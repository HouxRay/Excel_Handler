"""AI 对齐辅助 — Excel 白名单加载、目标日期识别"""
import re

from openpyxl import load_workbook


def load_excel_whitelist(excel_path: str, sheet_name: str = None) -> dict:
    """从 Excel 表头读取 JC 编号白名单。

    Returns: {编号: (队伍A, 队伍B)}
    复用 read_header_bases 的格式：[编号, 队伍A, 队伍B, 空]
    """
    if not excel_path:
        return {}
    from src.Excel_Handler import ExcelHandler
    try:
        handler = ExcelHandler(excel_path, sheet_name)
        bases = handler.read_header_bases()
        whitelist = {}
        for base in bases:
            code = base[0]
            team_a = base[1] or ""
            team_b = base[2] or ""
            if code is not None and str(code).strip():
                whitelist[str(code).strip()] = (team_a, team_b)
        return whitelist
    except Exception:
        return {}


def load_bd_whitelist(excel_path: str, sheet_name: str = None) -> dict:
    """从 BD Excel 表头读取 BD 号白名单。

    Returns: {BD号: (队伍A, 队伍B)}
    复用 find_bd_columns 的结构。
    """
    if not excel_path:
        return {}
    try:
        wb = load_workbook(excel_path, read_only=True, data_only=True)
        if sheet_name and sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
        else:
            ws = wb.active
        from src.BD_Handler import find_bd_columns
        col_map = find_bd_columns(ws)
        wb.close()
        whitelist = {}
        for code_num, info in col_map.items():
            teams = info.get("teams", ["", ""])
            whitelist[str(code_num)] = (teams[0] or "", teams[1] or "")
        return whitelist
    except Exception:
        return {}


def detect_target_date(html_text: str) -> str:
    """从文本识别目标日期（如"周二"）。

    扫描 周[一二三四五六日]，返回最常见的。
    """
    if not html_text:
        return ""
    matches = re.findall(r'周[一二三四五六日]', html_text)
    if not matches:
        return ""
    # 返回出现最多的星期
    from collections import Counter
    return Counter(matches).most_common(1)[0][0]


def extract_codes_from_text(html_text: str) -> set:
    """提取文本中实际出现的比赛编号（周二001 / 北单N）。

    只匹配带明确比赛前缀的编号（周二/周三等星期前缀，或"北单"前缀），
    避免误把正文中的普通数字（如身价 818、排名 870）当成编号。
    用于后端校验 AI 输出，防止 AI 幻觉补全。
    """
    codes = set()
    if not html_text:
        return codes
    # JC: 周二001 / 周二 001 / 周001 等（必须有星期前缀）
    for m in re.finditer(r'周[一二三四五六日]\s*(\d{3})', html_text):
        codes.add(m.group(1).lstrip('0').zfill(3))
    # 表头/标题常见："竞彩004+005+007"、"004+005+007"（用 + 连接）
    for m in re.finditer(r'竞彩\s*([\d+]{3,})', html_text):
        for part in re.findall(r'\d{3}', m.group(1)):
            codes.add(part)
    # BD: 北单1, 北单4
    for m in re.finditer(r'北单\s*(\d+)', html_text):
        codes.add(m.group(1))
    return codes


def extract_bd_code_from_filename(filename: str) -> str:
    """从 BD 文件名提取 BD 号。'北单63冰岛超....html' → '63'"""
    if not filename:
        return ""
    m = re.search(r'北单(\d+)', filename)
    return m.group(1) if m else ""


def filter_hallucinations(predictions: list, text_codes: set, whitelist: dict,
                          mode: str = 'jc') -> list:
    """丢弃不在'文本实际出现编号'∩'白名单'内的预测。

    防止 AI 把白名单当选择题填满，输出文本未提到的编号。
    mode='jc'：编号补零到3位匹配；mode='bd'：纯数字直接匹配。
    """
    if not predictions:
        return []
    valid = text_codes & set(whitelist.keys()) if whitelist else text_codes
    filtered = []
    for p in predictions:
        code = str(p.get('code', '')).strip()
        if mode == 'bd':
            ok = code in valid  # BD：纯数字，不做补零
        else:
            ok = code.lstrip('0').zfill(3) in valid  # JC：补零到3位
        if ok:
            filtered.append(p)
    return filtered
