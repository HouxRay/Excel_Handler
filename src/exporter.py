"""导出/排序 — 收集写入操作和统计数据"""
from collections import Counter, defaultdict
from src.Excel_Writer import ExcelWriter


def collect_export_write_ops(get_info, data_storage, selected_item, ex_header,
                              is_pic, excel_first_columns, logger):
    """
    收集并验证导出写入操作。
    Returns: (write_ops, invalid_items)
        write_ops: [(line, col, [values]), ...]
        invalid_items: [str, ...]  无效数据描述列表
    """
    write_ops = []
    invalid_items = []

    for code, values in data_storage[selected_item].items():
        try:
            line_location, column_location = get_info.get_location(
                code, ex_header, excel_first_columns
            )
            if line_location is None or column_location is None:
                logger.error(f"get_location 返回 None for code={code}, ex_header={ex_header}")
                continue

            validated_vals = []
            for val in values:
                if is_pic:
                    if val is None or str(val).strip() == "":
                        validated_vals.append('')
                    else:
                        validated_vals.append(str(val).strip())
                else:
                    result = ExcelWriter.validate_value(val)
                    if result['valid']:
                        validated_vals.append(result['converted'])
                    else:
                        validated_vals.append('')
                        if val is not None and str(val).strip() != "":
                            invalid_items.append(
                                f"code={code}, 值='{val}': {result['message']}"
                            )

            write_ops.append((line_location, column_location, validated_vals))

        except Exception as e:
            logger.exception(f"获取位置失败 - code: {code}")
            return [], invalid_items

    return write_ops, invalid_items


def collect_sort_stats(data_storage, pic_categories, logger):
    """
    收集排序统计数据（HTML/图片模式）。
    Returns: dict_counter {number: {value: count, ...}, ...}
    """
    stats = defaultdict(Counter)
    logger.info("开始排序")

    for name in data_storage:
        if name in pic_categories:
            continue
        number_dict = data_storage[name]
        for number, values in number_dict.items():
            for value in values:
                if value.strip() and value.strip().isdigit():
                    stats[number][value] += 1

    return {number: dict(counts.most_common()) for number, counts in stats.items()}
