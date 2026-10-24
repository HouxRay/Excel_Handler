"""AI 预测结果存储 — 保存/加载历史结果，供复用与核对"""
import json
import os
from datetime import datetime

AI_DIR = os.path.join("json", "ai")


def save_ai_result(result: dict, source_file: str = "", mode: str = "") -> str:
    """保存 AI 结果到 json/ai/<日期>/，返回文件路径"""
    # 按日期分子目录
    date_dir = os.path.join(AI_DIR, datetime.now().strftime("%Y-%m-%d"))
    os.makedirs(date_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(source_file or "unknown"))[0]
    # 文件名清洗（去掉非法字符）
    base = "".join(c if c.isalnum() or c in "-_" else "_" for c in base)
    path = os.path.join(date_dir, f"ai_{ts}_{base}.json")

    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file": source_file,
        "mode": mode,
        "method": result.get("method", ""),
        "raw": result.get("raw", ""),
        "predictions": result.get("predictions", []),
        # 实际送入 AI 的提示词（system + user），供排查
        "prompt": result.get("prompt", []),
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_ai_results() -> list[dict]:
    """加载所有已保存的 AI 结果（按时间倒序，递归所有日期子目录）。

    Returns: [{"filepath", "timestamp", "source_file", "mode", "predictions_count"}]
    """
    if not os.path.isdir(AI_DIR):
        return []
    results = []
    # 遍历所有日期子目录（兼容旧的直接放在根目录的 json）
    entries = sorted(os.listdir(AI_DIR), reverse=True)
    for entry in entries:
        path = os.path.join(AI_DIR, entry)
        if os.path.isdir(path):
            # 日期子目录
            for fname in sorted(os.listdir(path), reverse=True):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(path, fname)
                _append_result(results, fpath)
        elif entry.endswith(".json"):
            # 旧的根目录 json
            _append_result(results, path)
    return results


def _append_result(results: list, path: str):
    """辅助：加载单个 AI 结果文件并加入列表"""
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
        pass


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
