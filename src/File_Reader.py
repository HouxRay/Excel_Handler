import os
from pathlib import Path
from typing import List, Union

class FileReader:
    def __init__(self, recursive: bool = True, file_path: str = None):
        """
        :param recursive: 是否递归遍历子目录，默认开启
        :param file_path: 指定文件路径，如果指定，则只读取该文件

        """
        self.recursive = recursive
        self.file_path = file_path

    def get_all_files(self, target_path: Union[str, Path]) -> List[str]:
        """
        获取路径下所有文件
        :param target_path: 需要遍历的路径
        :return: 包含完整路径的文件列表
        """
        if not os.path.exists(target_path):
            raise ValueError(f"路径不存在: {target_path}")
        
        if not os.path.isdir(target_path):
            return [str(Path(target_path).resolve())]

        file_list = []
        base_path = Path(target_path)
        
        if self.recursive:
            # 递归遍历模式
            for file in base_path.rglob("*"):
                if self._is_valid_file(file):
                    file_list.append(str(file.resolve()))
        else:
            # 非递归模式
            for item in base_path.iterdir():
                if self._is_valid_file(item):
                    file_list.append(str(item.resolve()))
        
        file_test = sorted(file_list, key=lambda x: self._get_pinyin_prefix(Path(x).name))
        
        return sorted(file_list, key=lambda x: self._get_pinyin_prefix(Path(x).name))


# 新增辅助方法（需要安装pypinyin库：pip install pypinyin）
    def _get_pinyin_prefix(self, filename: str) -> str:
        """获取文件名首字符的拼音首字母"""
        from pypinyin import pinyin, Style
        
        first_char = filename[0]
        # 如果是汉字则转换拼音
        if '\u4e00' <= first_char <= '\u9fff':
            return pinyin(first_char, style=Style.FIRST_LETTER)[0][0].upper()
        return first_char.upper()
    

    def _is_valid_file(self, path: Path) -> bool:
        """验证是否为有效文件（过滤目录和非HTML文件）"""
        return path.is_file() and path.suffix.lower() == '.html'
    
    @staticmethod
    def extract_filename(file_path: Union[str, Path]) -> str:
        """
        智能文件名提取方法
        示例输入：D:\ExcelHander\src\2025-03-03-竞彩\优选计划.html
        返回结果：优选计划
        """
        path_obj = Path(file_path)
        
        # 处理带扩展名的情况
        if path_obj.suffix:
            # 使用两次rsplit确保处理多重扩展名（如.tar.gz）
            return path_obj.name.rsplit('.', 1)[0]
        return path_obj.name
    

    def extract_file(self, files_path) -> None:
        """
         提取文件名
        """
        found_files = self.get_all_files(files_path)
        files = []
        for _, file in enumerate(found_files, 1):
            files.append(self.extract_filename(file))

        return files
    
    def file_dict(self):
        """
        读取文件名并返回字典
        """
        found_files = self.get_all_files(self.file_path)
        files = {}
        for _, file in enumerate(found_files, 1):
            files[self.extract_filename(file)] = file

        return files
            
# 使用示例
if __name__ == "__main__":
    # 创建读取器（默认递归模式）
    reader = FileReader()
    
    # 获取当前目录下所有文件
    files = reader.get_all_files("src\\2025-03-03-竞彩")
    print("找到文件列表：")
    for idx, file in enumerate(files, 1):
        print(f"{idx}. {file}  ->  {reader.extract_filename(file)}")
    
    print(reader.file_dict())