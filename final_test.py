#!/usr/bin/env python3
"""
最终测试 - 验证乱序表头数字支持和参数顺序修复
"""
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_excel_info_class():
    """测试Excel_Info类的修改"""
    print("=== 测试Excel_Info类的修改 ===")
    print()
    
    # 导入模块
    try:
        from Excel_Info import GetWriteInfo
        print("✓ 成功导入GetWriteInfo类")
    except Exception as e:
        print(f"✗ 导入失败: {e}")
        return False
    
    # 测试文件路径
    test_html_dir = "src/2025-03-03-竞彩"
    test_excel_file = "src/sample.xlsx"
    
    # 检查文件是否存在
    if not os.path.exists(test_html_dir):
        print(f"✗ HTML文件夹不存在: {test_html_dir}")
        test_html_dir = input("请输入HTML文件夹路径: ")
    
    if not os.path.exists(test_excel_file):
        print(f"✗ Excel文件不存在: {test_excel_file}")
        test_excel_file = input("请输入Excel文件路径: ")
    
    try:
        # 创建实例
        print(f"\n创建GetWriteInfo实例...")
        ew = GetWriteInfo(test_html_dir, test_excel_file)
        print("✓ 实例创建成功")
        
        # 测试表头数字映射
        print(f"\n测试表头数字映射:")
        if hasattr(ew, 'header_num_to_column'):
            print(f"✓ header_num_to_column属性存在")
            print(f"  找到 {len(ew.header_num_to_column)} 个表头数字映射")
            
            # 显示映射
            for num, col in sorted(ew.header_num_to_column.items()):
                print(f"    表头数字 {num} -> 列 {col}")
        else:
            print("✗ header_num_to_column属性不存在")
            return False
        
        # 测试get_location方法
        print(f"\n测试get_location方法:")
        
        # 测试1: 只传递表头数字
        print(f"\n1. 测试只传递表头数字:")
        test_nums = ["001", "002", "003"]
        for num in test_nums:
            try:
                line, col = ew.get_location(excel_first_num=num)
                print(f"  表头数字 {num}: 列位置 = {col}")
            except Exception as e:
                print(f"  表头数字 {num}: 错误 - {e}")
        
        # 测试2: 获取文件映射信息
        print(f"\n2. 测试获取文件映射信息:")
        try:
            files_names, excel_first_columns = ew.get_file_and_excel_info()
            print(f"  ✓ 获取到 {len(files_names)} 个文件名")
            print(f"  ✓ 获取到Excel列名映射")
            
            # 测试3: 获取映射
            mapping = ew.get_mapping()
            if mapping:
                print(f"  ✓ 获取到 {len(mapping)} 个映射")
                
                # 测试前几个映射
                print(f"\n3. 测试完整映射:")
                test_count = min(3, len(mapping))
                for i, (key, value) in enumerate(list(mapping.items())[:test_count]):
                    try:
                        line, col = ew.get_location(
                            mapping_value=key,
                            excel_first_num=value,
                            excel_first_columns=excel_first_columns
                        )
                        print(f"  映射 {i+1}: '{key}' -> '{value}' -> 位置(行{line}, 列{col})")
                    except Exception as e:
                        print(f"  映射 {i+1}: '{key}' -> '{value}' -> 错误: {e}")
            else:
                print(f"  ✗ 未获取到映射")
                
        except Exception as e:
            print(f"  ✗ 获取文件映射信息失败: {e}")
            import traceback
            traceback.print_exc()
        
        return True
        
    except Exception as e:
        print(f"✗ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parameter_order():
    """测试参数顺序修复"""
    print("\n" + "="*60)
    print("=== 测试参数顺序修复 ===")
    print()
    
    print("分析table_qt.py中的调用:")
    print("-"*40)
    
    # 读取table_qt.py中的相关代码
    table_qt_path = "window/table_qt.py"
    if os.path.exists(table_qt_path):
        with open(table_qt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找get_location调用
        for i, line in enumerate(lines):
            if 'get_location' in line:
                print(f"第{i+1}行: {line.strip()}")
                
                # 检查参数顺序
                if 'get_location(ex_header, key, self.excel_name)' in line:
                    print("  ✗ 错误的参数顺序: ex_header在前，key在后")
                    print("    应该改为: get_location(key, ex_header, self.excel_name)")
                elif 'get_location(key, ex_header, self.excel_name)' in line:
                    print("  ✓ 正确的参数顺序: key在前，ex_header在后")
                elif 'get_location(excel_first_num=' in line:
                    print("  ✓ 使用关键字参数，顺序正确")
    else:
        print(f"✗ 文件不存在: {table_qt_path}")
    
    return True

def create_summary():
    """创建修改总结"""
    print("\n" + "="*60)
    print("=== 修改总结 ===")
    print()
    
    summary = """
    已完成的修改:
    
    1. Excel_Info.py 修改:
       - 添加了 header_num_to_column 属性来存储表头数字到列位置的映射
       - 添加了 _build_header_num_mapping() 方法构建映射关系
       - 修改了 get_location() 方法支持乱序表头数字
         * 优先使用映射查找表头数字的实际列位置
         * 回退到旧逻辑保持兼容性
         * 添加调试输出便于问题排查
    
    2. table_qt.py 修改:
       - 修复了 get_location() 调用参数顺序错误
         * 原调用: get_location(ex_header, key, self.excel_name)
         * 修复后: get_location(key, ex_header, self.excel_name)
         * 确保文件名用于查找行，表头数字用于计算列
    
    3. 备份:
       - 已备份原始工程到 ExcelHander_backup_*
       - 已备份原始 Excel_Info.py 到 Excel_Info.py.backup
    
    功能改进:
    - 支持乱序表头数字（如001,003,002,005）
    - 保持向后兼容性，连续表头数字仍可正常工作
    - 添加调试输出帮助排查问题
    
    注意事项:
    1. 程序现在会在初始化时构建表头数字映射
    2. 对于乱序表头，使用映射查找实际列位置
    3. 对于连续表头，回退到旧逻辑计算列位置
    4. 参数顺序已修复，确保正确查找行和列位置
    """
    
    print(summary)

def main():
    print("ExcelHander 乱序表头数字支持 - 最终测试")
    print("="*60)
    
    # 测试Excel_Info类的修改
    test_excel_info_class()
    
    # 测试参数顺序修复
    test_parameter_order()
    
    # 创建修改总结
    create_summary()
    
    print("\n" + "="*60)
    print("测试完成！")
    print("\n下一步建议:")
    print("1. 运行程序进行实际测试")
    print("2. 使用包含乱序表头数字的Excel文件测试")
    print("3. 验证所有现有功能仍然正常工作")
    print("4. 检查调试输出以确保映射正确构建")

if __name__ == "__main__":
    main()