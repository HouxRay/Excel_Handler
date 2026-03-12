import src.Excel_Handler as eh
import src.File_Reader as fr
from typing import Union, List, Dict
from pathlib import Path

class NameMatcher:
    def __init__(self, file_path: Union[str, Path], excel_path: Union[str, Path], match_mode: str = "contains"):
        """
        中文专用列表匹配器
        
        :param match_mode: 匹配模式
            - "contains"：子字符串包含模式（默认）
            - "startswith"：开头匹配模式
            - "endswith"：结尾匹配模式
        """
        self.file_path = file_path
        self.file_reader = fr.FileReader(file_path)
        self.excel_handler = eh.ExcelHandler(excel_path)
        self.match_mode = match_mode
        self._validate_mode()

    def name_extractor(self) -> List[str]:
        files_names = self.file_reader.extract_file(self.file_path)
        excel_first_columns = self.excel_handler.read_first_column()
        return files_names, excel_first_columns

    def _validate_mode(self):
        """验证匹配模式有效性"""
        valid_modes = ["contains", "startswith", "endswith"]
        if self.match_mode not in valid_modes:
            raise ValueError(f"无效匹配模式，可选：{valid_modes}")

    def create_mapping(self, list1: List[str] = None, list2: List[str] = None) -> Dict[str, str]:
        """
        创建中文匹配字典
        """
        mapping = {}
        if list1 is None or list2 is None:
            list1, list2 = self.name_extractor()
        processed_list2 = {item: item for item in list2}  # 中文无需处理大小写

        for short in list1:
            matches = []
            
            for full in list2.keys():
                # 直接使用原字符串进行匹配
                if self._match_check(short, full):
                    matches.append(full)
            
            if len(matches) == 1:
                mapping[short] = matches[0]
        
        return mapping
    
    def create_mapping_v2(self, file_names: List[str] = None, pre_mapping: Dict[str, str] = None) -> Dict[str, str]:
        """
        创建自定义匹配字典
        """
        if file_names is None:
            file_names, _ = self.name_extractor()
        new_dict = {}
        # 筛选出存在于 original_dict 的键值对
        for key in file_names:
            if key not in pre_mapping:
                continue
            new_dict[key] = pre_mapping[key]
        return new_dict

    def _match_check(self, short: str, full: str) -> bool:
        """执行实际匹配检查"""
        if self.match_mode == "contains":
            return short in full
        elif self.match_mode == "startswith":
            return full.startswith(short)
        elif self.match_mode == "endswith":
            return full.endswith(short)
        return False
    

class AdvancedChineseMatcher(NameMatcher):
    def __init__(self, similarity=0.8, **kwargs):
        """
        支持中文模糊匹配
        """
        super().__init__(**kwargs)  # 修复此处，传递所有关键字参数
        self.similarity = similarity

    def _match_check(self, short: str, full: str) -> bool:
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, short, full).ratio()
        return ratio >= self.similarity


# 验证示例
if __name__ == "__main__":
    # 测试数据
    list1 = ['红龙', '单关女皇', '财神密码', '八神竞猜']  # 注意使用英文引号
    list2 = ['胜喜红龙', '单关女皇1314', '彩神密码', '八神竞猜']
    excel_path = ("src\sample.xlsx")
    file_path = ("src\\2025-03-03-竞彩")
    matcher = NameMatcher(file_path, excel_path)

    pre_mapping = {}
    with open("mapping/mapping_data.txt", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()  # 去除首尾空格和换行
            if line and "：" in line:
                value, key = line.split("：", 1)  # 只分割第一个冒号
                pre_mapping[key.strip()] = value.strip()
    # # 创建匹配器（默认包含模式）
    # matcher = NameMatcher()
    result = matcher.create_mapping()  # 输出：{'红龙': '胜喜红龙', '单关女皇': '单关女皇1314', '八神竞猜': '八神竞猜'}
    result2 = matcher.create_mapping_v2(pre_mapping=pre_mapping)
    
    print("匹配结果：")
    for k, v in result.items():
        print(f"{k} → {v}")
    # 预期输出：红龙、单关女皇、八神竞猜

    print("="*50)
    amatcher = AdvancedChineseMatcher(similarity=0.5, file_path=file_path, excel_path=excel_path)
    result = amatcher.create_mapping()  # 输出：{'财神': '彩神'}
    for k, v in result.items():
        print(f"{k} → {v}")