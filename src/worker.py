from PyQt5.QtCore import QObject, pyqtSignal


class ExcelWriteWorker(QObject):
    """Excel 写入工作线程，在主线程收集操作后，在后台线程执行写入"""

    finished = pyqtSignal(bool, str)   # (是否成功, 消息)
    progress = pyqtSignal(int, int)    # (当前, 总数)

    def __init__(self, excel_path, sheet_name, write_ops):
        """
        write_ops: [(line, col, value), ...]
            value 类型支持: str / int / list (横向写入) / dict (纵向写入)
        """
        super().__init__()
        self.excel_path = excel_path
        self.sheet_name = sheet_name
        self.write_ops = write_ops

    def run(self):
        try:
            from src.Excel_Writer import ExcelWriter

            writer = ExcelWriter(self.excel_path, self.sheet_name)
            total = len(self.write_ops)

            for i, (line, col, value) in enumerate(self.write_ops):
                if isinstance(value, list):
                    writer.batch_write_list(line, col, value)
                elif isinstance(value, dict):
                    writer.batch_write_dict(line, col, value)
                else:
                    writer.batch_write_cell(line, col, value)
                self.progress.emit(i + 1, total)

            writer.save()
            self.finished.emit(True, "写入完成")

        except Exception as e:
            self.finished.emit(False, f"写入失败: {str(e)}")
