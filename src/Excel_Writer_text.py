from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from pathlib import Path
import re

class ExcelWriter:
    def __init__(self, file_path):
        """
        Excel数据写入器
        :param file_path: Excel文件路径
        """
        self.file_path = Path(file_path)
        self.wb = load_workbook(filename=self.file_path)
        self.ws = self.wb.active

    def parse_input(self, data_str: str) -> tuple:
        """
        解析输入字符串
        示例输入："001； 八神竞猜：12 11；波姐： 00 11；财神密码： 12 01； 逸都： 11 12"
        返回：("001", {"八神竞猜": ["12", "11"], ...})
        """
        # 分割主要部分
        parts = [p.strip() for p in data_str.split('；') if p.strip()]
        
        # 提取编号
        code = parts[0]
        
        # 解析数据条目
        data_dict = {}
        pattern = r"([\u4e00-\u9fa5]+)\s*:\s*(\d+)\s+(\d+)"
        
        for part in parts[1:]:
            match = re.match(pattern, part)
            if match:
                name = match.group(1)
                values = [match.group(2), match.group(3)]
                data_dict[name] = values
        
        return code, data_dict

    def calculate_column(self, code: str) -> int:
        """
        计算起始列号
        公式：code_number * 4 + 1
        """
        try:
            code_number = int(code)
            return code_number * 4 + 1
        except ValueError:
            raise ValueError(f"无效的编号格式: {code}")

    def write_data(self, dict_data: dict, data_str: str):
        """
        执行数据写入
        :param dict_data: 行号映射字典 {"名称": 行号}
        :param data_str: 数据输入字符串
        """
        # 解析输入数据
        code, value_data = self.parse_input(data_str)
        
        # 计算起始列
        start_col = self.calculate_column(code)
        
        # 遍历写入数据
        for name, values in value_data.items():
            if name in dict_data:
                row = dict_data[name]
                # 写入两个相邻列
                for i, value in enumerate(values):
                    col_letter = get_column_letter(start_col + i)
                    self.ws[f"{col_letter}{row}"] = value
        
        self._save()

    def _save(self):
        """保存文件"""
        self.wb.save(self.file_path)

# 使用示例
if __name__ == "__main__":
    # 初始化数据
    row_mapping = {
        '八神竞猜': 2,
        '波姐': 3,
        '财神密码': 4,
        '逸都': 36
    }
    
    input_data = "001； 八神竞猜：12 11；波姐： 00 11；财神密码： 12 01； 逸都： 11 12"

    # 执行写入
    writer = ExcelWriter("src/sample3.xlsx")
    writer.write_data(row_mapping, input_data)
    print("数据写入完成")