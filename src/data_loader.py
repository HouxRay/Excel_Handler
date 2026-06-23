"""数据加载模块 — 图片配置、JSON 加载、数据初始化"""
import json
import os
import re


def load_pic_config(data_storage, flag, top_data):
    """
    加载图片模式配置（mapping/mapping_pic.txt）
    Returns: (pic_categories, pic_mapping, data_storage)
    """
    pic_categories = []
    pic_mapping = {}
    try:
        pic_file = "mapping/mapping_pic.txt"
        if os.path.exists(pic_file):
            with open(pic_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "：" in line:
                        value, key = line.split("：", 1)
                        pic_mapping[key.strip()] = value.strip()
                        pic_categories.append(key.strip())
            for pic_cat in pic_categories:
                if pic_cat not in data_storage:
                    if flag:
                        data_storage[pic_cat] = {row[0]: list(row[2:]) for row in top_data}
                    else:
                        data_storage[pic_cat] = {}
    except Exception:
        pass
    return pic_categories, pic_mapping, data_storage


def load_json_to_storage(json_path, get_info, data_storage, logger):
    """
    加载 JSON 文件到 data_storage。自动识别 BD/新/旧格式。
    Returns: (data_storage, bd_json_restore)
        bd_json_restore 不为 None 时表示 JSON 为 BD 格式。
    """
    bd_json_restore = None
    try:
        if get_info is not None:
            json_data = get_info.get_json(json_path)
        else:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)

        if json_data and isinstance(json_data, dict):
            first_key = next(iter(json_data))
            first_val = json_data[first_key]
            # BD 格式：{label: {code, home, away, scores}}
            if isinstance(first_val, dict) and "code" in first_val and "scores" in first_val:
                bd_json_restore = json_data
                logger.info(f"JSON 识别为 BD 格式: {len(json_data)} 场比赛")
            elif isinstance(first_val, dict) and re.match(r'\d{3}', str(first_key)):
                # 新格式：{code: {category: [scores]}}
                imported_count = 0
                for code, categories in json_data.items():
                    for category, scores in categories.items():
                        if category in data_storage:
                            data_storage[category][code] = scores
                            imported_count += 1
                        else:
                            data_storage[category] = {code: scores}
                            imported_count += 1
                logger.info(f"成功从JSON文件加载数据: {imported_count} 项")
            else:
                # 旧格式：{category: {code: [scores]}}
                data_storage.update(json_data)
                logger.info("成功从JSON文件加载额外数据（旧格式）")
    except Exception as e:
        logger.exception("加载JSON数据时发生错误")
    return data_storage, bd_json_restore


def load_bd_json(bd_json_path, logger):
    """
    加载 BD 专属 JSON 文件。
    Returns: dict or None
    """
    try:
        with open(bd_json_path, 'r', encoding='utf-8') as f:
            bd_json_data = json.load(f)
        if bd_json_data and isinstance(bd_json_data, dict):
            logger.info(f"BD JSON 加载成功: {len(bd_json_data)} 场比赛")
            return bd_json_data
    except Exception as e:
        logger.exception("加载BD JSON数据时发生错误")
    return None


def reinitialize_data(file_path, excel_path, sheet_name, mapping_path, logger):
    """
    用新路径重新创建 GetWriteInfo 并初始化所有数据。
    Returns: dict 包含 get_info, top_data, left_items, excel_name,
             fixed_values, mapping, header_bases, url, data_storage
    """
    from src.Excel_Info import GetWriteInfo
    from src.Excel_Writer import ExcelWriter

    get_info = GetWriteInfo(file_path, excel_path, sheet_name, mapping_path)
    top_data = get_info.get_tabel_info()
    left_items, excel_name = get_info.get_file_and_excel_info()

    fixed_values = {row[0]: row[1] for row in top_data}
    mapping = get_info.get_mapping()
    header_bases = get_info.get_header_bases()
    url = get_info.get_file_dict()

    data_storage = {item: {row[0]: list(row[2:]) for row in top_data}
                    for item in left_items}

    return {
        'get_info': get_info,
        'top_data': top_data,
        'left_items': left_items,
        'excel_name': excel_name,
        'fixed_values': fixed_values,
        'mapping': mapping,
        'header_bases': header_bases,
        'url': url,
        'data_storage': data_storage,
    }
