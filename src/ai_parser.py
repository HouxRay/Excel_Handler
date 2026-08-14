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
        # 规范化 scores 为分组格式（每组=一个机构的比分组）
        for p in preds:
            if "scores" in p:
                p["scores"] = _normalize_scores_groups(p["scores"])
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
