"""无界面宿主对象：让服务版复用桌面版的编排逻辑（``BatchRunnerMixin``）

## 它是什么

``BatchRunnerMixin`` 要求宿主提供一组**纯数据属性**（见 ``src/service/batch_runner.py`` 文档）。
桌面版由 ``EnhancedDataEditor`` 提供；服务版由本模块的 :class:`ServiceContext` 提供。

**不做任何 GUI 事**：不建窗口、不弹窗、不刷新表格。

## 数据中枢从哪来

复用桌面版同一条初始化链路（已确认**均无 Qt 依赖**）：

- :func:`src.data_loader.reinitialize_data` —— 一次给出
  ``get_info / top_data / left_items / fixed_values / mapping / header_bases / url / data_storage``
- :func:`src.data_loader.load_pic_config` —— 图片类别的数据与映射
- :func:`src.BD_Handler.load_bd_config` —— 北单比赛清单与比分（含 HTML 解析）

## 与桌面版的唯一差异

``selected_item_name()`` 不读左侧单选列表，而是**用任务参数指定的目标**
（客户要求"直接填入我选中的那个预测者"，服务版由调用方明确告知是谁）。
"""
import os
from src.sources.BD_Handler import load_bd_config
from src.excel.data_loader import load_pic_config, reinitialize_data
from src.common.log_setup import logger
from src.service.batch_runner import BatchRunnerMixin


class ServiceContext(BatchRunnerMixin):
    """把"一次任务的目标位置 + 数据中枢"包装成 mixin 可用的宿主"""

    def __init__(self, spec: dict, bd_json_restore: dict = None):
        """
        Args:
            spec: :meth:`ServiceConfig.resolve_target` 的返回值，需含
                ``mode`` / ``excel_path`` / ``html_dir`` / ``mapping_path`` / ``target_name``
            bd_json_restore: 北单 JSON 恢复数据（可选，等价于桌面版"导入 BD JSON"）
        """
        self.mode = (spec.get("mode") or "jc").lower()
        # html=JC/HTML 模式；pic=图片模式；bd=北单模式
        self.data_mode = "bd" if self.mode == "bd" else ("pic" if self.mode == "pic" else "html")

        self.excel_path = spec.get("excel_path") or ""
        self.sheet_name = spec.get("sheet") or None
        # 图片模式允许不给 html_dir；但初始化时行号映射需要一个**存在的**目录，
        # 缺省时回落到工作簿所在目录（Bug 2026-11-8_4）
        self.file_path = (spec.get("html_dir") or "").strip() or os.path.dirname(self.excel_path) or ""
        self.mapping_path = spec.get("mapping_path") or "mapping/mapping_data.txt"

        self.bd_excel_path = spec.get("bd_excel_path") or self.excel_path
        self.bd_sheet_name = spec.get("bd_sheet") or None
        self.bd_file_path = spec.get("bd_html_dir") or self.file_path

        #: 本任务的目标（机构 / 图片类别 / 比赛标签）；由任务参数给出
        self.target = spec.get("target_name") or ""

        self.is_dirty = False
        self.flag = True                   # 真实数据（与桌面版载入真实 Excel 后一致）
        self._bd_export_rows = {}          # {code: start_row} 北单导出起始行记账
        self._bd_json_restore = bd_json_restore

        self._load_data()
        if self.data_mode == "bd":
            self._load_bd()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _load_data(self):
        """构建数据中枢（复用桌面版同一条链路）"""
        result = reinitialize_data(self.file_path, self.excel_path,
                                   self.sheet_name, self.mapping_path, logger)
        self.get_info = result["get_info"]
        self.top_data = result["top_data"]
        self.left_items = result["left_items"]
        self.fixed_values = result["fixed_values"]
        self.mapping = result["mapping"]
        self.header_bases = result["header_bases"]
        self.url = result["url"]
        self.data_storage = result["data_storage"]
        self.excel_first_columns = result["excel_name"]
        if not self.excel_first_columns:
            # 早失败：否则会拖到提交阶段表现为"每个编号都定位失败"，极难排查
            from src.service.jobs import JobError
            raise JobError(
                "CONFIG_ERROR",
                f"工作簿行号映射为空（excel_path={self.excel_path!r}, sheet={self.sheet_name!r}）："
                "请确认工作表名正确、且该表 A 列有数据")

        # 图片类别（与桌面版一致：无论当前模式都会加载，供按需切换）
        self.pic_categories, self.pic_mapping, self.data_storage = load_pic_config(
            self.data_storage, True, self.top_data, logger)

        self.bd_categories = []
        self.bd_data_storage = {}

    def _load_bd(self):
        """加载北单比赛清单（解析北单 HTML 目录）"""
        self.bd_categories, self.bd_data_storage = load_bd_config(
            self.bd_excel_path, self.bd_file_path, self.bd_sheet_name,
            self._bd_json_restore, logger)

    # ------------------------------------------------------------------
    # BatchRunnerMixin 要求的方法
    # ------------------------------------------------------------------

    def selected_item_name(self) -> str:
        """服务版的"当前目标"：由任务参数给出，而不是界面选中项"""
        return self.target

    # 兼容 mixin 内部使用的旧名
    _selected_item_name = selected_item_name

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def known_codes(self, target: str = None) -> list:
        """某目标下已知的编号列表（供预览提示用）"""
        key = target if target is not None else self.target
        return sorted((self.data_storage.get(key) or {}).keys())

    def load_existing_values(self) -> int:
        """把工作簿里**已有的**数据读进 ``data_storage``（供"排序"这类只读动作）

        **为什么需要**：服务版每个任务都新建上下文，``data_storage`` 初始是空槽，
        而排序统计的是"表里已有的比分" → 不载入则统计恒为 0（Bug 2026-11-8_6）。

        **只用于排序/汇总 JSON**，不能用于 extract —— 否则"不覆盖已有值"会把
        新数据全部当成"已有"而跳过。

        Returns: 实际载入的编号条数
        """
        import openpyxl

        filled = 0
        try:
            wb = openpyxl.load_workbook(self.excel_path, read_only=True, data_only=True)
            ws = wb[self.sheet_name] if self.sheet_name else wb.active
        except Exception:
            logger.exception(f"载入工作簿失败，排序将按空数据统计: {self.excel_path}")
            return 0
        try:
            for item in list(getattr(self, "left_items", []) or []):
                ex_header = (self.mapping or {}).get(item)
                slots = self.data_storage.get(item)
                if not ex_header or not isinstance(slots, dict):
                    continue
                for code in list(slots.keys()):
                    try:
                        row, col = self.get_info.get_location(
                            code, ex_header, self.excel_first_columns)
                    except Exception:
                        continue
                    if row is None or col is None:
                        continue
                    try:
                        vals = [ws.cell(row=row, column=col + i).value for i in range(4)]
                    except Exception:
                        continue
                    if any(v not in (None, "") for v in vals):
                        slots[code] = ["" if v is None else str(v) for v in vals]
                        filled += 1
        finally:
            try:
                wb.close()
            except Exception:
                pass
        logger.info(f"已载入工作簿现有数据 {filled} 条（供排序统计）")
        return filled

    def describe(self) -> dict:
        """一行摘要（写日志/返回响应时用）"""
        return {
            "mode": self.data_mode,
            "target": self.target,
            "excel_path": self.excel_path,
            "sheet": self.sheet_name,
            "html_dir": self.file_path,
            "known_codes": len(self.known_codes()),
            "bd_matches": len(self.bd_data_storage) if self.data_mode == "bd" else 0,
        }


def build_context(spec: dict, bd_json_restore: dict = None) -> ServiceContext:
    """按任务参数构建宿主对象（构造失败会抛异常，由调用方转成错误码）"""
    return ServiceContext(spec, bd_json_restore=bd_json_restore)
