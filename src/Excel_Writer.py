from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from typing import List, Union
from src.Excel_Info import GetWriteInfo
from PyQt5.QtWidgets import QMessageBox, QApplication
import sys

MATCH_DICT={
    "s":"胜",
    'ss':'胜胜',
    "rs":"让胜",
    "f":"负",
    "rf":"让负",
    "p":"平",
    "rp":"让平",
    "sp":"双平",
    "q":"平",
    "rq":"让平",
    "sq":"双平",
    "fsf":"分胜负",
}

class ExcelWriter:
    def __init__(self, excel_path: str, sheet_name: str = None):
        """
        Excel 写入器
        :param excel_path: Excel 文件路径
        :param sheet_name: 要写入的工作表名称，如果为None则使用活动工作表
        """
        self.excel_path = excel_path
        self.workbook = load_workbook(self.excel_path)
        
        # 根据sheet_name参数选择工作表
        if sheet_name:
            # 检查工作表是否存在
            if sheet_name in self.workbook.sheetnames:
                self.ws = self.workbook[sheet_name]
            else:
                # 如果工作表不存在，创建它
                self.ws = self.workbook.create_sheet(title=sheet_name)
        else:
            # 如果没有指定sheet_name，使用活动工作表
            self.ws = self.workbook.active
        
        # 初始化 QApplication（如果不存在）
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication(sys.argv)

    @staticmethod
    def validate_value(item: str) -> dict:
        """
        纯验证方法，无UI弹窗。可在主线程预先验证。
        返回: {'valid': bool, 'message': str, 'converted': str}
        """
        if not item or str(item).strip() == "":
            return {'valid': False, 'message': '数据不能为空', 'converted': ''}
        item_str = str(item).strip()
        if item_str.isdigit():
            if len(item_str) != 2:
                return {'valid': False, 'message': f'数字必须为2位，当前为{len(item_str)}位: "{item_str}"', 'converted': item_str}
            return {'valid': True, 'message': '验证通过', 'converted': item_str}
        if item_str.lower() in MATCH_DICT:
            return {'valid': True, 'message': '验证通过', 'converted': MATCH_DICT[item_str.lower()]}
        return {'valid': False, 'message': f'字符不在允许列表中: "{item_str}"', 'converted': item_str}

    def _validate_item(self, item: str) -> dict:
        """
        验证数据项是否符合要求
        
        参数:
        - item: 要验证的数据项
        
        返回:
        - dict: {'valid': bool, 'message': str}
        """
        if not item or item.strip() == "":
            return {'valid': False, 'message': '数据不能为空'}
        
        item_str = str(item).strip()
        
        # 检查是否为数字
        if item_str.isdigit():
            if len(item_str) != 2:
                return {'valid': False, 'message': f'数字必须为2位，当前为{len(item_str)}位: "{item_str}"'}
            return {'valid': True, 'message': '验证通过'}
        
        # 检查是否在match_dict中
        match_dict = MATCH_DICT
        
        if item_str.lower() in match_dict:
            return {'valid': True, 'message': '验证通过'}
        else:
            return {'valid': False, 'message': f'字符不在允许列表中: "{item_str}"，允许的字符: {list(match_dict.keys())}'}

    def batch_write_cell(self, line_location: int, column_location: int, value) -> None:
        """静默写入单个单元格，无验证、无弹窗、不保存"""
        match_dict = MATCH_DICT
        item = str(value).strip() if value is not None else ""
        if item.lower() in match_dict:
            item = match_dict[item.lower()]
        self.ws.cell(row=line_location, column=column_location).value = item

    def batch_write_list(self, line_location: int, column_location: int, values: list) -> None:
        """静默写入列表（横向连续），无验证、无弹窗、不保存"""
        match_dict = MATCH_DICT
        for idx, item in enumerate(values):
            if item is None or item == "":
                continue
            item_str = str(item).strip()
            if item_str.lower() in match_dict:
                item_str = match_dict[item_str.lower()]
            self.ws.cell(row=line_location, column=column_location + idx).value = item_str

    def batch_write_dict(self, line_location: int, column_location: int, value: dict) -> None:
        """静默写入字典（纵向连续），无验证、无弹窗、不保存"""
        current_line = line_location
        for idx, (key, val) in enumerate(value.items()):
            if val is None or val == "":
                continue
            self.ws.cell(row=current_line + idx, column=column_location).value = key
            self.ws.cell(row=current_line + idx, column=column_location + 1).value = val

    def save(self):
        """显式保存工作簿"""
        self.workbook.save(self.excel_path)

    def write_info(self, line_location: int,
                   column_location: int,
                   value: Union[int, str, list, dict], # dict is testing
                   cheak_empty: bool = False) -> None:
        """
        向 Excel 写入数据，如果目标单元格已有非空字符串则跳过

        参数:
        - line_location: 行号（从1开始）
        - column_location: 列号（从1开始）
        - value: 要写入的数据（支持 int/str/list/dict 类型）（注：dict仅支持统计时使用，且在测试中）
        - cheak_empty: 是否检查空值，默认 False
        """
        
        match_dict=MATCH_DICT
        
        try:
            if isinstance(value, list):
                # 处理列表数据（横向连续写入）
                if not any(value):  # 遇到空值停止写入
                    return  1# 直接退出不写入
                for idx, item in enumerate(value):
                    if item is None or item == "":  # 遇到空值跳过
                        continue
                    
                    # 验证数据
                    validation_result = self._validate_item(item)
                    if not validation_result['valid']:
                        # 显示验证失败的提示
                        message = f"位置 ({line_location}, {column_location + idx}) 写入失败:\n{validation_result['message']}\n\n是否继续写入其他数据？"
                        reply = QMessageBox.question(self.app.activeWindow(), '验证失败', message,
                                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if reply == QMessageBox.No:
                            return  0# 用户选择不继续
                        continue  # 跳过这个项目
                    
                    # 计算当前单元格位置
                    current_col = column_location + idx
                    target_cell = self.ws.cell(row=line_location, column=current_col)
                    
                    # 检查单元格是否已有非空字符串
                    if isinstance(target_cell.value, str) and target_cell.value.strip() and cheak_empty:
                        print(f"跳过写入 ({line_location}, {current_col}): 已有数据 '{target_cell.value}'")
                        continue
                    
                    if item.lower() in match_dict.keys():
                        item = match_dict[item.lower()]
                    # 写入并保存
                    target_cell.value = item
                self.workbook.save(self.excel_path)
                return  1# 写入成功

            elif isinstance(value, (int, str)):
                # 处理单个数据（int/str）
                # 验证数据
                validation_result = self._validate_item(str(value))
                if not validation_result['valid']:
                    # 显示验证失败的提示
                    message = f"位置 ({line_location}, {column_location}) 写入失败:\n{validation_result['message']}\n\n是否取消写入？"
                    reply = QMessageBox.question(self.app.activeWindow(), '验证失败', message,
                                               QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                    if reply == QMessageBox.Yes:
                        return  0 # 用户选择取消写入
                
                # 显示确认对话框
                position = f"({line_location}, {column_location})"
                display_value = str(value)
                message = f"确认写入到位置 {position}？\n数据: {display_value}"
                if str(value).lower() in match_dict.keys():
                    message += f" -> {match_dict[str(value).lower()]}"
                
                reply = QMessageBox.question(self.app.activeWindow(), '确认写入', message,
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.No:
                    return  0# 用户取消写入
                
                target_cell = self.ws.cell(row=line_location, column=column_location)

                # 检查单元格是否已有非空字符串
                if isinstance(target_cell.value, str) and target_cell.value.strip() and cheak_empty:
                    print(f"跳过写入 ({line_location}, {column_location}): 已有数据 '{target_cell.value}'")
                    return  0# 直接退出不写入

                # 写入并保存
                if str(value).lower() in match_dict.keys():
                    target_cell.value = match_dict[str(value).lower()]
                else:
                    target_cell.value = value
                self.workbook.save(self.excel_path)
                return  1# 写入成功

            elif isinstance(value, dict):
                current_line = line_location
                current_col = column_location  
                # 处理字典数据（纵向连续写入）
                for idx, (key, val) in enumerate(value.items()):
                    if val is None or val == "":  # 遇到空值停止写入  key: 001 val:{'12': 2, '22': 2, '42': 2, '33': 1, '15': 1, '41': 1, '25': 1}
                        continue

                    # 计算当前单元格位置
                    current_line = line_location + idx
                    target_score = self.ws.cell(row=current_line, column=current_col)
                    target_count = self.ws.cell(row=current_line, column=current_col + 1)
                    target_score.value = key
                    target_count.value = val
                self.workbook.save(self.excel_path)
                return  1# 写入成功

            else:
                raise ValueError("不支持的数据类型，仅允许 int/str/list/dict")

        except Exception as e:
            print(f"写入 Excel 失败: {e}")
            raise  # 可根据需要改为更精细的错误处理



if __name__ == "__main__":
    file_path = "src\\2025-03-03-竞彩"
    excel_path = "src/sample3.xlsx"
    writer = ExcelWriter(excel_path)
    writer.write_info(1,1,0)