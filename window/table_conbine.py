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
    
    folder_path, excel_path, json_path, sheet_name, bd_folder = path_selector.selected_paths

    # 验证路径有效性
    if not excel_path:
        QMessageBox.critical(None, "错误", "必须选择有效的Excel文件路径")
        return
    if not folder_path and not bd_folder:
        QMessageBox.critical(None, "错误", "必须选择 HTML 文件夹路径或北单文件夹路径")
        return

    # 保存路径到 QSettings 配置
    from PyQt5.QtCore import QSettings
    settings = QSettings("config.ini", QSettings.IniFormat)
    if not settings.value("paths/mapping_path"):
        settings.setValue("paths/mapping_path", "mapping/mapping_data.txt")
    settings.setValue("paths/html_folder_path", folder_path)
    settings.setValue("paths/excel_path", excel_path)
    settings.setValue("paths/json_path", json_path)
    settings.setValue("paths/sheet_name", sheet_name)
    settings.setValue("paths/bd_folder_path", bd_folder or "")

    try:
        # 第二步：获取表格信息

        # 第三步：显示主窗口
        main_window = EnhancedDataEditor(excel_path = excel_path,
                                         file_path = folder_path,
                                         json_path = json_path,
                                         sheet_name = sheet_name,
                                         bd_file_path = bd_folder or "")
        main_window.show()
        
        sys.exit(app.exec_())
        
    except Exception as e:
        QMessageBox.critical(None, "初始化错误", f"初始化失败: {str(e)}")

if __name__ == "__main__":
    run()