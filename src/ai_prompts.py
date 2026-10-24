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
    # 目标日期硬约束：从 ai_config 读取（真实今天或用户临时覆盖）
    weekday = ai_config.get_target_weekday()
    date_hint = f"今天是{weekday}。只输出 {weekday} 的比赛，其他星期的比赛一律丢弃。\n"

    user_text = f"""请分析以下预测文本，提取比赛结果。

{date_hint}
【目标比赛清单】（编号、队伍）
{whitelist_str}

【规则】
1. 只输出预测文本中【明确给出预测】的比赛
2. 目标清单只用于验证编号是否合法，绝不用于补全
3. 文本未提到的比赛，绝对不要输出（即使它在目标清单中）
4. 以编号为准识别比赛，队伍名可能有翻译差异，忽略
5. 若某预测对应不了清单中的编号，丢弃
6. 比分只保留 2 位数字；胜平负只保留中文
7. 宁可少输出，不可多输出（避免幻觉）
8. 输出 JSON 格式：{{"predictions": [{{"code": "001", "scores": ["20","21"], "wdl": ["胜"]}}]}}

【预测文本】
{markdown_text}"""
    return [
        {"role": "system", "content": ai_config.get_system_prompt()},
        {"role": "user", "content": user_text},
    ]


def build_bd_messages(markdown_text: str, whitelist: dict,
                      target_date: str = "", target_bd_code: str = "") -> list[dict]:
    """BD 模式：给定 BD 号白名单，让 AI 对齐输出

    whitelist: {BD号: (队伍A, 队伍B)} 来自 BD Excel 表头
    target_bd_code: 当前文件的 BD 号（如"63"），只输出该号的预测
    """
    code_hint = ""
    if target_bd_code:
        code_hint = f"【当前比赛 BD 号】{target_bd_code}\n只输出 BD 号 {target_bd_code} 的比分预测。\n"

    user_text = f"""请分析以下预测文本，提取北单（BD）比赛的比分预测。

{code_hint}
请按以下格式逐行输出每个机构的比分预测：

机构名：北单号 比分1 比分2 ...

【规则】
1. 只输出 BD 号 {target_bd_code if target_bd_code else ''} 的比赛
2. 每行格式：机构名 + 冒号 + 北单号 + 该机构对【当前目标比赛】的比分（2位数字，用空格分隔，个数不限）
3. 没有名字的机构，标注为 None1、None2、None3...（依次递增，区分不同实例，不要合并）
4. 不同机构即使比分相同也要分别列出（机构不同）
5. 关键：若文本中某机构的比分对应的是【其他北单号】的比赛（如北单1、北单2），而不是当前目标号 {target_bd_code if target_bd_code else ''}，必须丢弃，不要输出
6. 注意区分多组比赛，确保编号与比分匹配
7. 不要输出胜平负（胜/负/平）、队伍名、赔率等多余内容
8. 最后用 JSON 包装：{{"predictions": [{{"label": "机构名", "code": "{target_bd_code if target_bd_code else ''}", "scores": ["01","12"]}}, ...]}}

【预测文本】
{markdown_text}"""
    return [
        {"role": "system", "content": ai_config.get_system_prompt_bd()},
        {"role": "user", "content": user_text},
    ]
