from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

class ExcelHandler:
    def __init__(self, file_path, sheet_name: str = None):
        self.file_path = file_path
        self.wb = load_workbook(filename=file_path, read_only=True, data_only=True)
        
        # 使用指定的sheet或活动sheet
        if sheet_name and sheet_name in self.wb.sheetnames:
            self.ws = self.wb[sheet_name]
        else:
            self.ws = self.wb.active
            if sheet_name:
                print(f"警告: sheet '{sheet_name}' 不存在，使用活动sheet: {self.ws.title}")
    
    def read_first_column(self):
        """读取第一列数据（从第二行开始）"""
        column_data = {}
        empty_counter = 0
        current_row = 2  # 从第二行开始
        
        for row in self.ws.iter_rows(min_row=2, max_col=1):
            cell_value = row[0].value
            
            if cell_value in (None, ""):
                empty_counter += 1
                if empty_counter > 2:
                    break
            else:
                empty_counter = 0
                column_data[cell_value] = current_row
            
            current_row += 1
        
        return column_data

    def read_header_bases(self):
        """读取表头基准（从第二列开始）"""
        bases = []
        invalid_counter = 0
        current_col = 2  # 从B列开始
        
        while True:
            # 获取当前基准的四列范围
            base_cols = [current_col + i for i in range(4)]
            
            # 检查是否超出表格范围
            if base_cols[-1] > self.ws.max_column:
                break
            
            # 获取基准四列的值
            base_values = [
                self.ws.cell(row=1, column=col).value
                for col in base_cols
            ]
            
            # 验证基准格式
            if self._is_valid_base(base_values):
                bases.append(base_values)
                invalid_counter = 0  # 有效基准重置计数器
            else:
                # 检查是否符合"数字 空 空 空"格式
                if self._is_number_with_empty(base_values):
                    invalid_counter += 1
                    bases.append(base_values)
                else:
                    invalid_counter = 0
                
                # 超过两个无效基准时停止
                if invalid_counter >= 2:
                    break
            
            current_col += 4
        
        return bases

    def _is_valid_base(self, values):
        """验证基准格式：数字 文字 文字 空"""
        try:
            # 验证数字列
            if not isinstance(values[0], (int, float)):
                if not str(values[0]).isdigit():
                    return False
            
            # 验证文字列
            for i in range(1, 3):
                if values[i] in (None, ""):
                    return False
            
            # 验证空列
            if values[3] not in (None, ""):
                return False
            
            return True
        except IndexError:
            return False

    def _is_number_with_empty(self, values):
        """验证格式：数字 空 空 空"""
        try:
            # 验证数字列
            if not isinstance(values[0], (int, float)):
                if not str(values[0]).isdigit():
                    return False
            
            # 验证后三列为空
            for i in range(1, 4):
                if values[i] not in (None, ""):
                    return False
            
            return True
        except IndexError:
            return False

# 使用示例
if __name__ == "__main__":
    handler = ExcelHandler("src\sample2.xlsx")
    
    # 读取第一列数据
    first_col_data = handler.read_first_column()
    print("第一列数据：", first_col_data)
    
    # 读取表头基准
    header_bases = handler.read_header_bases()
    print("有效基准：")
    for i, base in enumerate(header_bases):
        print(f"基准{i+1}: {base}")