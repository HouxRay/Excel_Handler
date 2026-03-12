import Excel_Handler as eh
import File_Reader as fr
from typing import Union
from pathlib import Path

class NameMatcher:
    def __init__(self, file_path:str, excel_path:str):
        self.file_path = file_path
        self.file_reader = fr.FileReader(file_path)
        self.excel_handler = eh.ExcelHandler(excel_path)

    def match_names(self):
        match_dict = {}
        files_names = self.file_reader.extract_file(self.file_path)
        excel_first_columns = self.excel_handler.read_first_column()
        for excel_first_column in excel_first_columns:
            if excel_first_column in files_names:
                match_dict.keys
        #         print(f"{excel_first_column} is matched")
        #     else:
        #         print(f"{excel_first_column} is not matched")

if __name__ == "__main__":    
    excel_path = ("src\sample.xlsx")
    file_path = ("src\\2025-03-03-竞彩")
    name_matcher = NameMatcher(file_path, excel_path)
    name_matcher.match_names()