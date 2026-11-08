import os

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
            from src.excel.Excel_Writer import ExcelWriter

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


class BatchAIWorker(QObject):
    """批量 AI 提取工作线程：逐文件调用 AI，实时发信号，支持协作式取消。

    设计约束（线程安全）：
    - ``jobs`` 必须是主线程拷贝好的纯数据快照 ``[(名称, 绝对路径), ...]``；
      本对象在子线程内只使用这些纯数据与传入的白名单，**不访问主窗口(self)、
      不创建/操作任何 Qt 控件**，主线程通过信号更新界面与内存数据。
    - ``whitelist`` 由主线程预加载后传入并逐文件复用，避免每个文件都重新读
      一遍 Excel（单文件流程仍是每次加载，互不影响）。
    """

    started_item = pyqtSignal(int, int, str)   # 序号(从1起), 总数, 名称
    item_done = pyqtSignal(int, str, dict)     # 序号, 名称, AI 结果
    item_failed = pyqtSignal(int, str, str)    # 序号, 名称, 错误信息
    finished = pyqtSignal(list, bool)          # 失败清单[(名称, 错误)], 是否被取消

    def __init__(self, jobs, mode: str, whitelist: dict):
        super().__init__()
        self.jobs = list(jobs)
        self.mode = mode
        self.whitelist = whitelist if whitelist is not None else {}
        self._cancelled = False

    def cancel(self):
        """协作式取消：只置标志位，当前文件会跑完（最坏等一次 AI 超时）"""
        self._cancelled = True

    def run(self):
        from src.ai import ai_alignment
        from src.ai import ai_handler
        from src.ai import ai_storage

        failed = []
        total = len(self.jobs)

        for i, (label, path) in enumerate(self.jobs, 1):
            if self._cancelled:
                break

            self.started_item.emit(i, total, label)
            try:
                # BD 模式：从文件名取目标 BD 号，逐文件做硬约束
                target_bd_code = ""
                if self.mode == 'bd':
                    target_bd_code = ai_alignment.extract_bd_code_from_filename(
                        os.path.basename(path))

                result = ai_handler.extract_predictions_from_html(
                    path,
                    mode=self.mode,
                    target_bd_code=target_bd_code,
                    whitelist=self.whitelist,
                )

                # JSON① 落档（与单文件流程一致；落档失败不影响填入）
                try:
                    ai_storage.save_ai_result(result, source_file=path, mode=self.mode)
                except Exception:
                    pass

                self.item_done.emit(i, label, result)

            except Exception as e:
                failed.append((label, str(e)))
                self.item_failed.emit(i, label, str(e))

        self.finished.emit(failed, self._cancelled)
