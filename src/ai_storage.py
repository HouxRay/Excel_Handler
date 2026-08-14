"""AI 预测结果存储 — 保存/加载历史结果，供复用与核对"""
import json
import os
from datetime import datetime

AI_DIR = os.path.join("json", "ai")


def save_ai_result(result: dict, source_file: str = "", mode: str = "") -> str:
    """保存 AI 结果到 json/ai/，返回文件路径"""
    os.makedirs(AI_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(source_file or "unknown"))[0]
    # 文件名清洗（去掉非法字符）
    base = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
    path = os.path.join(AI_DIR, f"ai_{ts}_{base}.json")

    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file": source_file,
        "mode": mode,
        "method": result.get("method", ""),
        "raw": result.get("raw", ""),
        "predictions": result.get("predictions", []),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_ai_results() -> list[dict]:
    """加载所有已保存的 AI 结果（按时间倒序）。

    Returns: [{"filepath", "timestamp", "source_file", "mode", "predictions_count"}]
    """
    if not os.path.isdir(AI_DIR):
        return []
    results = []
    for fname in sorted(os.listdir(AI_DIR), reverse=True):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(AI_DIR, fname)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            results.append({
                "filepath": path,
                "timestamp": data.get("timestamp", ""),
                "source_file": data.get("source_file", ""),
                "mode": data.get("mode", ""),
                "predictions_count": len(data.get("predictions", [])),
            })
        except Exception:
            continue
    return results


def load_ai_result(path: str) -> dict:
    """加载单个 AI 结果文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def load_ai_results_filtered(date_filter: str = "", file_filter: str = "") -> list[dict]:
    """按日期和文件名筛选加载历史 AI 结果。

    date_filter: 'YYYY-MM-DD' 或 ''(全部)
    file_filter: 机构名(HTML文件名去扩展名) 或 ''(全部)
    """
    results = load_ai_results()
    filtered = []
    for r in results:
        if date_filter and not r["timestamp"].startswith(date_filter):
            continue
        if file_filter:
            fname = os.path.splitext(os.path.basename(r["source_file"]))[0]
            if fname != file_filter:
                continue
        filtered.append(r)
    return filtered


def get_available_filenames() -> list[str]:
    """从历史记录提取所有机构文件名（去扩展名，去重）"""
    seen = set()
    names = []
    for r in load_ai_results():
        fname = os.path.splitext(os.path.basename(r["source_file"]))[0]
        if fname and fname not in seen:
            seen.add(fname)
            names.append(fname)
    return names
