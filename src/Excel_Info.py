import src.Excel_Handler as Excel_Handler
import src.File_Reader as File_Reader
from src.Name_Matcher import NameMatcher
from openpyxl import load_workbook
from pathlib import Path


class GetWriteInfo:
    def __init__(self, file_path: str | Path, excel_path: str | Path,
                 sheet_name: str = None, mapping_path: str = "mapping/mapping_data.txt"):
        """
        file_path: html文件路径
        excel_path: excel文件路径
        sheet_name: Excel sheet名称，如果为None则使用活动sheet
        mapping_path: 映射文件路径，默认 mapping/mapping_data.txt
        """

        self.file_path = file_path
        self.excel_path = excel_path
        self.sheet_name = sheet_name
        self.file_reader = File_Reader.FileReader(file_path = file_path)
        self.excel_handler = Excel_Handler.ExcelHandler(excel_path, sheet_name)
        self.name_matcher = NameMatcher(file_path=file_path, excel_path=excel_path)
        self.file_path = Path(file_path)
        self.wb = load_workbook(filename=self.excel_path)

        # 使用指定的sheet或活动sheet
        if sheet_name and sheet_name in self.wb.sheetnames:
            self.ws = self.wb[sheet_name]
        else:
            self.ws = self.wb.active
            if sheet_name:
                print(f"警告: sheet '{sheet_name}' 不存在，使用活动sheet: {self.ws.title}")
        self.pre_mapping = {}
        with open(mapping_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()  # 去除首尾空格和换行
                if line and "：" in line:
                    value, key = line.split("：", 1)  # 只分割第一个冒号
                    self.pre_mapping[key.strip()] = value.strip()
        
        # 新增：构建表头数字到列位置的映射
        self.header_num_to_column = {}
        self._build_header_num_mapping()
        
    
    def get_file_and_excel_info(self):
        """
        获取文件列表与excel表格第一列数据
        """
        try:
            # 尝试调用 NameMatcher 实例的 name_extractor 方法
            files_names, excel_first_columns = self.name_matcher.name_extractor()
            return files_names, excel_first_columns
        except Exception as e:
            # 捕获并处理可能出现的异常
            print(f"An error occurred while extracting names: {e}")
            return [], []
        
        
    def get_header_bases(self):
        """
        获取excel表格的表头基准
        """
        try:
            # 尝试调用 ExcelHandler 实例的 read_header_bases 方法
            header_bases = self.excel_handler.read_header_bases()
            return header_bases
        except Exception as e:
            # 捕获并处理可能出现的异常
            print(f"An error occurred while reading header bases: {e}")
            return []
        
    def get_tabel_info(self):
        """
        获取表格基本信息
        """
        try:
            tabel_info = []
            # 尝试调用 ExcelHandler 实例的 read_header_bases 方法
            header_bases = self.excel_handler.read_header_bases()
            for info in header_bases:
                if info[1] == None or info[1] == '':
                    continue
                temp = info[:3]
                if info[2] is not None and info[2] != '':
                    temp[1] = info[1]+"vs"+info[2]    
                    temp.pop()
                else:
                    temp[1] = info[1]
                    temp.pop()         
                while 1:
                    temp.append('')
                    if len(temp) == 7:
                        break
                tabel_info.append(temp)

            return tabel_info
        except Exception as e:
            # 捕获并处理可能出现的异常
            print(f"An error occurred while reading header bases: {e}")
            return []
        

    def get_mapping(self):
        """
        获取匹配结果
        """
        try:
            # 尝试调用 NameMatcher 实例的 create_mapping 方法
            files_names, _ = self.get_file_and_excel_info()
            mapping = self.name_matcher.create_mapping_v2(files_names, self.pre_mapping)
            return mapping  # 返回映射结果
        except Exception as e:
            # 捕获并处理可能出现的异常
            print(f"An error occurred while creating mapping: {e}")
            return {}  # 返回空字典表示映射失败


    def get_location(self, header_num: str = None, file_key: str = None, excel_first_columns: dict = None) -> tuple:
        """
        获取写入信息的坐标 
        支持乱序表头数字（如001,003,002,005）
        
        Args:
            file_key: 文件键名，用于在excel_first_columns中查找行位置
            header_num: 表头数字（如'001', '002'），用于计算列位置
            excel_first_columns: 字典，键为文件键名，值为行号
            
        Returns:
            tuple: (行位置, 列位置) 或 None
        """     
        try:  
            # 检查必需参数
            if not header_num:
                print(f"ERROR: header_num 不能为空")
                return None
                
            if file_key and excel_first_columns:
                if file_key not in excel_first_columns:
                    print(f"ERROR: file_key '{file_key}' 不在 excel_first_columns 中")
                    return None
                    
                line_location = excel_first_columns[file_key]
            else:
                line_location = None
            
            # 计算列位置
            column_location = None
            
            # 首先尝试新逻辑：查找表头数字对应的实际列位置
            if header_num in self.header_num_to_column:
                header_col = self.header_num_to_column[header_num]
                # 数据列在表头列的右侧，每4列一组
                column_location = header_col
                # print(f"DEBUG: 使用新逻辑: 表头数字 {header_num} -> 表头列 {header_col} -> 数据列 {column_location}")
            else:
                # 回退到旧逻辑（保持兼容性）
                print(f"DEBUG: header_num '{header_num}' 不在 header_num_to_column 中")
                try:
                    # 尝试将header_num转换为整数
                    header_int = int(header_num)
                    column_location = (header_int - 1) * 4 + 2
                    print(f"DEBUG: 使用旧逻辑: 表头数字 {header_num} -> 数据列 {column_location}")
                except ValueError as ve:
                    print(f"ERROR: 无法将 header_num '{header_num}' 转换为整数: {ve}")
                    # 如果无法转换为整数，尝试其他格式
                    if header_num.isdigit():
                        # 如果是数字字符串但不是整数格式
                        try:
                            header_int = int(header_num.lstrip('0'))  # 去除前导零
                            column_location = (header_int - 1) * 4 + 2
                            print(f"DEBUG: 使用去除前导零逻辑: {header_num} -> {header_int} -> 数据列 {column_location}")
                        except:
                            print(f"ERROR: 无法处理 header_num '{header_num}'")
                            return None
                    else:
                        print(f"ERROR: header_num '{header_num}' 不是有效的数字")
                        return None
            
            if line_location is not None and column_location is not None:
                return line_location, column_location
            elif column_location is not None:
                return None, column_location
            else:
                return None
            
        except Exception as e:
            # 捕获并处理可能出现的异常
            print(f"ERROR: An error occurred while getting location: {e}")
            return None

    def _build_header_num_mapping(self):
        """
        构建表头数字到列位置的映射
        假设表头在第一行，每个表头包含3位数字（如001,002,003）
        """
        try:
            import re
            
            # 假设表头在第一行
            for col in range(1, self.ws.max_column + 1):
                cell_value = self.ws.cell(row=1, column=col).value
                if cell_value is not None:
                    # 处理各种格式的表头数字
                    header_num = None
                    
                    if isinstance(cell_value, str):
                        cell_str = cell_value.strip()
                        # 尝试提取3位数字
                        match = re.search(r'(\d{3})', cell_str)
                        if match:
                            header_num = match.group(1)
                        elif cell_str.isdigit():
                            # 如果是纯数字字符串，补零到3位
                            header_num = cell_str.zfill(3)
                        else:
                            # 尝试其他格式
                            match = re.search(r'\b(\d+)\b', cell_str)
                            if match:
                                num = match.group(1)
                                header_num = num.zfill(3)
                    
                    elif isinstance(cell_value, (int, float)):
                        # 数字类型，转换为3位字符串
                        header_num = str(int(cell_value)).zfill(3)
                    
                    # 如果找到表头数字，添加到映射
                    if header_num:
                        self.header_num_to_column[header_num] = col
            
            # 如果没有找到任何映射，创建默认映射
            if not self.header_num_to_column:
                # 假设表头数字从001开始，每4列一组
                for i in range(1, min(100, self.ws.max_column // 4 + 2)):
                    header_num = str(i).zfill(3)
                    col = (i - 1) * 4 + 1  # 表头列位置
                    if col <= self.ws.max_column:
                        self.header_num_to_column[header_num] = col
            
        except Exception as e:
            print(f"构建表头数字映射时出错: {e}")
            # 创建空映射
            self.header_num_to_column = {}
    
    def get_file_dict(self):
        """
        获取文件字典
        """
        try:
            # 尝试调用 File_Reader 实例的 file_dict 方法
            file_dict = self.file_reader.file_dict()
            return file_dict
        except Exception as e:
            # 捕获并处理可能出现的异常
            print(f"An error occurred while getting file dict: {e}")
            return {}  # 返回空字典表示文件字典获取失败
        
    def get_json(self, json_path):
        """
        获取json文件
        """
        import json
        # 读取JSON文件
        with open(json_path, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)

        return loaded_data


if __name__ == "__main__":
    ew = GetWriteInfo("src/2025-03-03-竞彩", "src/sample.xlsx")
    files_names, excel_first_columns = ew.get_file_and_excel_info()
    mapping = ew.get_mapping()
    # print(1)
    # print(ew.get_location(mapping_value="八神竞猜", excel_first_num="001", excel_first_columns = excel_first_columns))
    # print(files_names)
    # print('-'*50)
    # print(excel_first_columns)
    # print('-'*50)
    print(mapping)
    print(ew.pre_mapping)
    # print('-'*50)
    # print(ew.get_header_bases())
    # print('-'*50)
    # print(ew.get_tabel_info())
    # print('-'*50)
    # print(ew.get_file_dict())