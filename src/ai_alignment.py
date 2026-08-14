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
