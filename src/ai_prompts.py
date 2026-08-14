"""AI 提示词构建 — 支持白名单编号约束 + 目标日期"""
from src import ai_config


def _format_whitelist(whitelist: dict) -> str:
    """格式化白名单为多行文本 {编号: (队伍A, 队伍B)}"""
    lines = []
    for code, teams in whitelist.items():
        if isinstance(teams, (tuple, list)) and len(teams) >= 2:
            lines.append(f"{code}\t{teams[0]}\t{teams[1]}")
        else:
            lines.append(f"{code}")
    return "\n".join(lines)


def build_jc_messages(markdown_text: str, whitelist: dict,
                      target_date: str = "", ) -> list[dict]:
    """JC 模式：给定白名单编号+队伍，让 AI 对齐输出

    whitelist: {编号: (队伍A, 队伍B)} 来自 Excel 表头
    target_date: 目标日期描述（如"周二"），空则从内容识别
    """
    whitelist_str = _format_whitelist(whitelist)
    date_hint = f"目标比赛日期：{target_date}\n" if target_date else "目标比赛日期：从预测文本中识别\n"

    user_text = f"""请分析以下预测文本，提取比赛结果。

{date_hint}
【目标比赛清单】（编号、队伍）
{whitelist_str}

【规则】
1. 只输出目标清单中出现的编号
2. 以编号为准识别比赛，队伍名可能有翻译差异，忽略
3. 若文本中某预测对应不了清单中的编号，丢弃
4. 比分只保留 2 位数字；胜平负只保留中文
5. 输出 JSON 格式：{{"predictions": [{{"code": "001", "scores": ["20","21"], "wdl": ["胜"]}}]}}

【预测文本】
{markdown_text}"""
    return [
        {"role": "system", "content": ai_config.get_system_prompt()},
        {"role": "user", "content": user_text},
    ]


def build_bd_messages(markdown_text: str, whitelist: dict,
                      target_date: str = "") -> list[dict]:
    """BD 模式：给定 BD 号白名单，让 AI 对齐输出

    whitelist: {BD号: (队伍A, 队伍B)} 来自 BD Excel 表头
    """
    whitelist_str = _format_whitelist(whitelist)

    user_text = f"""请分析以下预测文本，提取北单（BD）比赛的预测结果。

【目标BD比赛清单】（编号、队伍）
{whitelist_str}

【规则】
1. 只输出目标清单中出现的 BD 编号
2. 以 BD 编号为准识别比赛，队伍名可能有翻译差异，忽略
3. 若文本中某机构预测的 BD 号与当前比赛不符，丢弃
4. 比分只保留 2 位数字
5. 输出 JSON 格式：{{"predictions": [{{"code": "1", "scores": ["20","21"], "wdl": ["胜"]}}]}}

【预测文本】
{markdown_text}"""
    return [
        {"role": "system", "content": ai_config.get_system_prompt_pic()},
        {"role": "user", "content": user_text},
    ]
