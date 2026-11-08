"""AI 返回解析模块 — 对齐 JC/BD 数据结构"""
import json
import re

# 标准化结构：
# {"predictions": [{"label": ..., "code": ..., "scores": [...], "home": ..., "away": ...}]}

# 行式文本解析正则（fallback）：编号（3位数字） + 胜平负 + 比分
_LINE_PATTERN = re.compile(
    r'(\d{3})\s+'
    r'([一-龥]+(?:\s+[一-龥]+)?)\s+'
    r'(\d{2}(?:\s+\d{2})?)'
)


def _extract_json(text: str) -> dict | None:
    """尝试从 AI 响应中提取 JSON 对象。"""
    # 优先找 { ... } 块
    start = text.find('{')
    if start == -1:
        return None
    # 尝试逐步匹配闭合括号
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return None
    return None


def _normalize_predictions(data: dict) -> list[dict]:
    """将 AI 返回的 JSON 规范化为 predictions 列表。

    支持两种输入形态：
    1. {"predictions": [...]}
    2. 直接 {"001": {...}} 或 {label: {...}}（直接是映射）
    """
    if not isinstance(data, dict):
        return []

    if "predictions" in data and isinstance(data["predictions"], list):
        return data["predictions"]

    # 尝试直接映射：key 为编号或机构名
    preds = []
    for key, val in data.items():
        if isinstance(val, dict):
            item = dict(val)
            item.setdefault("code", str(key))
            item.setdefault("label", str(key))
            preds.append(item)
    return preds


def _parse_line_fallback(response_text: str) -> list[dict]:
    """行式文本 fallback 解析（旧格式：编号 胜平负 比分）"""
    result = []
    for line in response_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('Part'):
            continue
        match = _LINE_PATTERN.search(line)
        if match:
            code = match.group(1)
            wdl = match.group(2).strip()
            scores = match.group(3).strip().split()
            scores = [s for s in scores if re.fullmatch(r'\d{2}', s)]
            result.append({
                "label": "",
                "code": code,
                "scores": scores,
                "wdl": wdl.split(),
                "home": "",
                "away": "",
            })
    return result


def _parse_bd_line(response_text: str) -> list[dict]:
    """解析 BD 行式输出：'机构名：北单号 比分1 比分2' → 每组比分。

    也兼容 JSON 包装：{"predictions": [{"label":..., "code":..., "scores":[...]}]}
    """
    # 先尝试 JSON
    data = _extract_json(response_text)
    if data is not None:
        preds = _normalize_predictions(data)
        for p in preds:
            if "scores" in p:
                p["scores"] = [str(s) for s in p["scores"] if str(s).strip()]
        return preds

    # 行式：机构名：北单号 比分...
    result = []
    for line in response_text.strip().splitlines():
        line = line.strip()
        if not line or '北单' not in line or '：' not in line:
            continue
        parts = line.split('：', 1)
        label = parts[0].strip()
        rest = parts[1]
        m = re.search(r'北单\s*(\d+)', rest)
        code = m.group(1) if m else ""
        scores = re.findall(r'\b\d{2}\b', rest)
        if scores:
            result.append({"label": label, "code": code, "scores": scores})
    return result


def _normalize_scores_groups(scores) -> list:
    """将 scores 规范化为 [组1, 组2, ...] 列表（每组是一个机构的多组比分）。

    AI 可能返回多种形态：
    - [["20","10"],["21"],["10","20","30"]] → 已是分组，原样保留（确保每组元素是str）
    - ["20","10","21","10","20","30"] → 平铺，无法区分机构分组，按原顺序每项独立一组
    - ["20","10"] → 单组
    """
    if not scores:
        return []
    if all(isinstance(s, (list, tuple)) for s in scores):
        # 已是分组，每组保留（转为 str）
        return [[str(x) for x in group] for group in scores]
    # 平铺：每项作为独立一组（AI 未分组时，保留每项）
    return [[str(s)] for s in scores if str(s).strip()]


def parse_ai_result(response_text: str, mode: str = 'jc') -> dict:
    """解析 AI 响应为标准化 dict。

    优先 JSON 解析，失败时回退到行式文本正则解析。
    mode='bd'：用 BD 行式/JSON 解析（机构：北单号 比分）
    返回：{"predictions": [...], "raw": "..."}
    """
    text = response_text or ""

    # BD 模式：专用解析
    if mode == 'bd':
        preds = _parse_bd_line(text)
        return {
            "predictions": preds,
            "raw": text,
            "method": "bd_line",
        }

    data = _extract_json(text)
    if data is not None:
        preds = _normalize_predictions(data)
        # JC 模式：保留原始平铺 scores（["21","11"]），不转分组
        return {
            "predictions": preds,
            "raw": text,
            "method": "json",
        }

    # fallback：行式文本
    preds = _parse_line_fallback(text)
    return {
        "predictions": preds,
        "raw": text,
        "method": "line",
    }


# ---------------------------------------------------------------------------
# 胜负平规范化（业务规则来自 2026-10-13 验收反馈）
#
# 图片里的「胜负平」列可能写成 `让胜（+1）`、`平让平（-1）`、`主负+平`，
# 而表格槽位只接受受限词表内的取值，且**不允许出现数字**。
# ---------------------------------------------------------------------------

#: 允许写入的胜负平取值（业务方给定的封闭词表，不允许其他）
WDL_ALLOWED = ("胜", "负", "平", "让平", "双平", "让胜", "让负")

#: 图面写法 → 词表内取值
_WDL_ALIASES = {
    "主胜": "胜", "客胜": "负",
    "主负": "负", "客负": "胜",
    "胜": "胜", "负": "负", "平": "平",
    "让胜": "让胜", "让负": "让负", "让平": "让平", "双平": "双平",
}

#: 一个格子里写了多个取值时的分隔符
_WDL_SEPARATORS = re.compile(r"[\s+,，、/|]+")


def _strip_wdl_noise(text: str) -> str:
    """去掉让球数与括号：``让胜（+1）`` → ``让胜``"""
    text = re.sub(r"[（(][^）)]*[）)]", "", text)   # 括号及其内容
    text = re.sub(r"[0-9]", "", text)                # 任何数字
    return text.strip()


def _tokenize_concat_wdl(text: str):
    """把紧连的写法拆成词表内的取值：``平让平`` → ``['平', '让平']``

    **只在含「让」或「双」时才尝试**：图面「半全场」列的取值都是
    ``平胜``/``胜胜``/``负负`` 这类纯 ``胜平负`` 组合，若不加限制，
    ``平胜`` 会被误拆成合法的 ``['平','胜']``，等于把半全场数据当胜负平写进去。
    宁可丢弃（由调用方记录告警）也不写错数据。

    Returns: 取值列表；无法完整识别时返回 None
    """
    if "让" not in text and "双" not in text:
        return None
    out = []
    i = 0
    while i < len(text):
        two = text[i:i + 2]
        if two in WDL_ALLOWED:
            out.append(two)
            i += 2
            continue
        one = text[i]
        if one in WDL_ALLOWED:
            out.append(one)
            i += 1
            continue
        return None                     # 出现无法识别的字符 → 整体放弃
    return out or None


def normalize_wdl(values) -> tuple:
    """把 AI 返回的胜负平规范化为受限词表内的取值。

    Returns: ``(accepted, dropped)``
        - ``accepted``：词表内的取值（保持原顺序、去重）
        - ``dropped``：无法识别而被丢弃的原始写法（供日志排查）
    """
    accepted, dropped = [], []
    # 模型偶尔对单值返回字符串而非列表（如 "让胜"）；若不包一层，
    # 下面的 for 会按字符迭代，把 "让胜" 拆成 "让"+"胜"
    if isinstance(values, str):
        values = [values]
    for raw in (values or []):
        text = _strip_wdl_noise(str(raw))
        if not text:
            continue

        parts = [p for p in _WDL_SEPARATORS.split(text) if p] or [text]
        tokens, ok = [], True
        for part in parts:
            token = _WDL_ALIASES.get(part)
            if token:
                tokens.append(token)
                continue
            sub = _tokenize_concat_wdl(part)
            if sub:
                tokens.extend(sub)
                continue
            ok = False
            break

        if ok and tokens:
            for token in tokens:
                if token not in accepted:
                    accepted.append(token)
        else:
            dropped.append(str(raw))

    return accepted, dropped
