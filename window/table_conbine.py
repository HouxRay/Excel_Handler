from window.table_qt import EnhancedDataEditor
from window.table_qt_2 import PathSelector
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog
from src.zip_handler import ensure_extracted, cleanup_temp_dirs
from src.log_setup import logger
import sys

def run():
    app = QApplication(sys.argv)

    # 第一步：获取路径
    path_selector = PathSelector()
    result = path_selector.exec_()  # 使用exec_()模态显示对话框

    if result != QDialog.Accepted:
        return  # 用户取消选择

    folder_path, excel_path, json_path, sheet_name, bd_folder, bd_excel, bd_sheet, bd_json = path_selector.selected_paths

    # 第二步：如果是 .zip 文件，自动解压到临时目录
    try:
        if folder_path:
            folder_path = ensure_extracted(folder_path, logger)
        if bd_folder:
            bd_folder = ensure_extracted(bd_folder, logger)
    except ValueError as e:
        QMessageBox.critical(None, "解压错误", str(e))
        return

    # 验证路径有效性
    # JC Excel 非必需（BD-only 场景），但 sheet 在提供了 Excel 时必需
    if not folder_path and not bd_folder:
        QMessageBox.critical(None, "错误", "必须选择 HTML 文件夹路径或北单文件夹路径")
        return

    # 保存 mapping_path 默认值（如果尚未设置）
    from PyQt5.QtCore import QSettings
    settings = QSettings("config.ini", QSettings.IniFormat)
    if not settings.value("paths/mapping_path"):
        settings.setValue("paths/mapping_path", "mapping/mapping_data.txt")

    try:
        # 显示主窗口（恢复上次的位置和大小）
        main_window = EnhancedDataEditor(excel_path=excel_path,
                                         file_path=folder_path,
                                         json_path=json_path,
                                         sheet_name=sheet_name,
                                         bd_file_path=bd_folder or "",
                                         bd_excel_path=bd_excel or "",
                                         bd_sheet_name=bd_sheet or "",
                                         bd_json_path=bd_json or "")
        # 恢复上次的窗口几何
        geom = settings.value("window/geometry")
        if geom:
            main_window.restoreGeometry(geom)
        main_window.show()

        # 退出时清理临时目录
        app.aboutToQuit.connect(lambda: cleanup_temp_dirs(logger))

        sys.exit(app.exec_())

    except Exception as e:
        QMessageBox.critical(None, "初始化错误", f"初始化失败: {str(e)}")

if __name__ == "__main__":
    run()