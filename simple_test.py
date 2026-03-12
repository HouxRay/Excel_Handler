#!/usr/bin/env python3
"""
简化测试 - 验证表头数字映射逻辑
"""
import re

# 模拟Excel表头行
def simulate_excel_headers():
    """模拟Excel表头行"""
    # 模拟乱序表头
    headers = [
        "001-项目A",      # 列1
        "003-项目C",      # 列2  
        "002-项目B",      # 列3
        "005-项目E",      # 列4
        "004-项目D",      # 列5
    ]
    
    header_num_to_column = {}
    
    for col_idx, header in enumerate(headers, 1):
        # 提取3位数字
        match = re.search(r'(\d{3})', header)
        if match:
            num = match.group(1)
            header_num_to_column[num] = col_idx
            print(f"表头 '{header}' -> 数字 {num} -> 列 {col_idx}")
    
    return header_num_to_column

def test_old_logic(excel_first_num):
    """测试旧逻辑"""
    column_location = (int(excel_first_num)-1) * 4 + 2
    return column_location

def test_new_logic(excel_first_num, header_num_to_column):
    """测试新逻辑"""
    if excel_first_num in header_num_to_column:
        header_col = header_num_to_column[excel_first_num]
        column_location = header_col + 1  # 数据在表头右侧第1列
        return column_location, True
    else:
        # 回退到旧逻辑
        column_location = (int(excel_first_num)-1) * 4 + 2
        return column_location, False

def main():
    print("=== 乱序表头数字支持测试 ===")
    print()
    
    # 模拟Excel表头
    print("模拟Excel表头（乱序）:")
    header_map = simulate_excel_headers()
    
    print("\n" + "="*50)
    print("测试结果对比:")
    print("="*50)
    
    test_numbers = ["001", "002", "003", "004", "005"]
    
    for num in test_numbers:
        old_col = test_old_logic(num)
        new_col, used_new_logic = test_new_logic(num, header_map)
        
        print(f"\n表头数字 {num}:")
        print(f"  旧逻辑计算列: {old_col}")
        print(f"  新逻辑计算列: {new_col} {'(使用映射)' if used_new_logic else '(回退到旧逻辑)'}")
        
        # 检查是否正确
        expected_col = None
        if num in header_map:
            expected_col = header_map[num] + 1
        
        if expected_col:
            print(f"  期望列位置: {expected_col}")
            print(f"  新逻辑是否正确: {'是' if new_col == expected_col else '否'}")
            print(f"  旧逻辑是否正确: {'是' if old_col == expected_col else '否'}")
    
    print("\n" + "="*50)
    print("结论:")
    print("-"*50)
    print("1. 旧逻辑假设表头数字连续，计算列位置为: (数字-1)*4+2")
    print("2. 新逻辑使用表头数字到列位置的映射，计算列位置为: 表头列+1")
    print("3. 对于乱序表头，新逻辑能正确找到位置，旧逻辑会出错")
    
    # 演示问题
    print("\n" + "="*50)
    print("问题演示:")
    print("-"*50)
    print("假设Excel表头顺序为: 001, 003, 002, 005, 004")
    print("旧逻辑对于002的计算: (2-1)*4+2 = 6")
    print("但实际上002在第3列，数据应该在列4")
    print("新逻辑会正确找到002在第3列，数据列=3+1=4")

if __name__ == "__main__":
    main()