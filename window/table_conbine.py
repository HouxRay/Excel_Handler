from window.table_qt import EnhancedDataEditor
from window.table_qt_2 import PathSelector
from src.Excel_Info import GetWriteInfo
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog
import sys

def run():
    app = QApplication(sys.argv)
    
    # 第一步：获取路径
    path_selector = PathSelector()
    result = path_selector.exec_()  # 使用exec_()模态显示对话框
    
    if result != QDialog.Accepted:
        return  # 用户取消选择
    
    folder_path, excel_path, json_path, sheet_name = path_selector.selected_paths
    
    # 验证路径有效性
    if not folder_path or not excel_path:
        QMessageBox.critical(None, "错误", "必须选择有效的文件夹和Excel文件路径")
        return
    
    try:
        # 第二步：获取表格信息
        # info_getter = GetWriteInfo(folder_path, excel_path)
        # top_data = info_getter.get_tabel_info()
        # files_names, excel_name = info_getter.get_file_and_excel_info()
        
        # 第三步：显示主窗口
        main_window = EnhancedDataEditor(excel_path = excel_path,
                                         file_path = folder_path,
                                         json_path = json_path,
                                         sheet_name = sheet_name)
        main_window.show()
        
        sys.exit(app.exec_())
        
    except Exception as e:
        QMessageBox.critical(None, "初始化错误", f"初始化失败: {str(e)}")

if __name__ == "__main__":
    run()