"""无 GUI 的编排逻辑（桌面版与无界面服务共用）

## 为什么用 mixin

桌面版的编排逻辑原来寄生在 ``window/table_qt.py`` 的 ``EnhancedDataEditor`` 里。
本模块把它们抽出来，供**两个入口共用**：

- 桌面入口：``EnhancedDataEditor(BatchRunnerMixin, QMainWindow)``
- 服务入口：无界面宿主类（只提供数据，不提供控件）

方法体与抽出前**逐字相同**（只把"显示/弹窗"这类 GUI 副作用拆到宿主），
因此桌面版行为不变——验收线是现有回归断言全绿。

## 宿主对象（``self``）必须提供

纯数据属性（**都不含 Qt 控件**）：

==============================  ==================================================
``data_mode``                   ``'html'`` / ``'pic'`` / ``'bd'``
``data_storage``                ``{机构或图片类别: {编号: [4 个槽位]}}``
``bd_data_storage``             ``{比赛标签: {code, home, away, scores, html_file}}``
``get_info``                    ``src.Excel_Info``（坐标计算）
``mapping`` / ``pic_mapping``   机构 / 图片类别的表头映射
``excel_path`` / ``sheet_name`` JC 目标工作簿与 sheet
``bd_excel_path`` / ``bd_sheet_name``    北单目标工作簿与 sheet
``left_items`` / ``url``        HTML 模式的机构清单与 机构→HTML 路径
==============================  ==================================================

宿主必须实现的方法：

- ``selected_item_name() -> str``：当前目标（桌面版读左侧选中项；服务版由任务参数给出）

## 不含 Qt

本模块只 import 标准库、``src.*`` 与 ``src.log_setup.logger``（与抽出前用的是同一个 logger）。
GUI 汇报（日志框、弹窗、刷新表格、后台线程）全部留在 ``window/table_qt.py`` 的薄包装里。
"""
import json
import os
import re
from datetime import datetime

from src import ai_alignment, ai_parser
from src.exporter import collect_export_write_ops, collect_sort_stats
from src.log_setup import logger


class BatchRunnerMixin:
    """批量/单文件 AI 填入的共用编排逻辑（无 GUI）"""

    # ------------------------------------------------------------------
    # 目标与白名单
    # ------------------------------------------------------------------

    def _batch_ai_mode(self) -> str:
        """当前数据模式对应的 AI 模式：'bd' 或 'jc'"""
        return 'bd' if self.data_mode == 'bd' else 'jc'

    def _current_whitelist(self) -> dict:
        """按当前模式加载 Excel 白名单（未配置则返回 {}）

        批量运行要求必须有白名单，故空字典即视为"未配置"。
        """
        if self.data_mode == 'bd':
            excel = self.bd_excel_path or self.excel_path or ""
            sheet = self.bd_sheet_name or self.sheet_name
            return ai_alignment.load_bd_whitelist(excel, sheet) if excel else {}
        if not self.excel_path:
            return {}
        return ai_alignment.load_excel_whitelist(self.excel_path, self.sheet_name)

    def _collect_batch_jobs(self):
        """构建批量任务清单（纯数据快照，供子线程使用）

        注意：方法名与实例属性 ``self._batch_jobs``（快照）区分，避免相互遮蔽。

        Returns: (jobs, pre_failed)
            jobs: [(名称, 绝对路径), ...]
            pre_failed: [(名称, 原因), ...]  没有对应源文件的条目
        """
        jobs, pre_failed = [], []
        if self.data_mode == 'bd':
            for label, info in self.bd_data_storage.items():
                path = info.get("html_file")
                if path and os.path.exists(path):
                    jobs.append((label, path))
                else:
                    pre_failed.append((label, "未找到对应的北单 HTML 文件"))
        else:
            url_map = getattr(self, 'url', None)
            for item in self.left_items:
                path = url_map.get(item) if isinstance(url_map, dict) else None
                if path and os.path.exists(path):
                    jobs.append((item, path))
                else:
                    pre_failed.append((item, "未找到对应的 HTML 文件"))
        return jobs, pre_failed

    # ------------------------------------------------------------------
    # 写入数据中枢
    # ------------------------------------------------------------------

    def _apply_ai_bd(self, predictions: list, overwrite: bool = True,
                     label_override: str = None) -> tuple:
        """BD 模式：写入 bd_data_storage（汇总所有机构的比分分组）

        overwrite=False（批量运行）时，目标比赛已有非空比分则整条跳过，不覆盖。
        label_override：批量运行直接指定比赛标签，不依赖 AI 返回的 code。
        Returns: (写入的比分组数, 跳过的比分组数)
        """
        all_groups = []
        code_target = None
        for pred in predictions:
            code = str(pred.get("code", ""))
            scores = pred.get("scores", [])
            if not code_target:
                code_target = code
            # 该机构的比分组（已是 2 位数字分组）
            group = [str(x).strip() for x in scores if str(x).strip().isdigit()]
            if group:
                all_groups.append(group)

        # 定位目标比赛：优先用批量传入的 label，其次按 code 匹配
        target_info = None
        if label_override and label_override in self.bd_data_storage:
            target_info = self.bd_data_storage[label_override]
        elif code_target:
            for info in self.bd_data_storage.values():
                if info.get("code") == code_target:
                    target_info = info
                    break

        if target_info is None:
            return 0, len(all_groups)

        # 禁止覆盖：已有非空比分 → 整条跳过
        if not overwrite:
            existing = target_info.get("scores") or []
            if any(any(str(v).strip() for v in g) for g in existing):
                return 0, len(all_groups)

        # 一次性写入该比赛的所有比分分组（保持原有行为）
        target_info["scores"] = all_groups
        return len(all_groups), 0

    def _apply_ai_jc(self, predictions: list, source_file: str = "",
                     overwrite: bool = True,
                     category_override: str = None,
                     with_wdl: bool = False) -> tuple:
        """JC / 图片模式：写入 data_storage

        overwrite=False（批量运行）时，目标单元格已有非空值则跳过，不覆盖。
        category_override：批量运行强制用遍历到的机构名，忽略 AI 返回的 label。
        with_wdl：槽位按 ``[胜负平1, 胜负平2, 比分1, 比分2]`` 组装（图片模式的约定，
            与 ``txt/<日期>/<类别>.txt`` 的写法一致）。**默认 False 保持 HTML 模式原行为不变。**
        Returns: (写入条数, 跳过条数)
        """
        # 机构名：优先 category_override，其次 pred 的 label/category，最后从文件名推断
        default_category = os.path.splitext(os.path.basename(source_file or ""))[0] if source_file else ""
        applied = 0
        skipped = 0
        wdl_written = 0
        for pred in predictions:
            category = (category_override or pred.get("label", "")
                        or pred.get("category", "") or default_category)
            code = str(pred.get("code", "")).zfill(3)
            scores = pred.get("scores", [])
            # 扁平化 scores
            flat = []
            for s in scores:
                if isinstance(s, list):
                    flat.extend(str(x).strip() for x in s)
                else:
                    flat.append(str(s).strip())
            vals = [x for x in flat if x]

            if with_wdl:
                # 胜负平规范化：只保留受限词表内的取值（详见 src/ai_parser.normalize_wdl）
                wdl, dropped = ai_parser.normalize_wdl(pred.get("wdl"))
                if dropped:
                    logger.warning(
                        f"胜负平取值不在允许词表内已丢弃 code={code}: {dropped}"
                        f"（允许：{'、'.join(ai_parser.WDL_ALLOWED)}）")
                vals = wdl[:2] + vals

            while len(vals) < 4:
                vals.append("")
            vals = vals[:4]

            if category not in self.data_storage or code not in self.data_storage[category]:
                skipped += 1
                continue

            # 禁止覆盖：目标已有非空值 → 跳过
            if not overwrite:
                current = self.data_storage[category][code]
                if any(str(v).strip() for v in current):
                    skipped += 1
                    continue

            self.data_storage[category][code] = vals
            applied += 1
            if with_wdl and vals[0]:
                wdl_written += 1

        if with_wdl:
            # 让"胜负平到底写进去多少条"可见（否则只能靠肉眼数表格）
            logger.info(f"胜负平写入 {wdl_written}/{applied} 条")
        return applied, skipped

    # ------------------------------------------------------------------
    # 编排 + 结果报告
    # ------------------------------------------------------------------

    def report_apply_result(self, applied: int, skipped: int, target_desc: str,
                            predictions: list) -> dict:
        """生成"AI 填入结果"的报告（写日志；**是否弹窗由宿主决定**）

        历史缺陷：单文件 AI 填入完全忽略写入结果，全部被跳过时界面上毫无提示。

        Returns: ``{"ok": bool, "line": str, "detail": str}``
            - ``ok=True``：``line`` 是成功摘要（宿主可显示到日志框）
            - ``ok=False``：``detail`` 是失败明细（宿主应弹窗告知用户）
        """
        codes = [str(p.get("code", "")).strip() for p in predictions
                 if str(p.get("code", "")).strip()]
        head = "、".join(codes[:10]) + ("…" if len(codes) > 10 else "")

        if applied:
            msg = f"AI 已填入 {target_desc}：写入 {applied} 条"
            if skipped:
                msg += f"，跳过 {skipped} 条"
            logger.info(msg)
            return {"ok": True, "line": "✅ " + msg, "detail": ""}

        detail = (f"目标位置：{target_desc}\n"
                  f"AI 返回编号：{head or '(无)'}\n"
                  f"被跳过：{skipped} 条")
        logger.warning(f"AI 填入未写入任何数据。{detail}")
        return {"ok": False, "line": "⚠️ AI 填入未写入任何数据，详情见日志", "detail": detail}

    def apply_predictions(self, predictions: list, source_file: str = "",
                          target_override: str = None) -> dict:
        """把确认的 AI 预测写入目标位置（纯逻辑，**不做任何 GUI 事**）

        目标位置一律取"当前选中项"：
        - 图片（选择文件 / 剪贴板粘贴 / 拖拽）的**文件名与预测者毫无关系**，
          过去靠文件名推导（如 ``image.png`` → ``"image"``）会全部落空；
        - HTML 文件名虽恰好等于机构名，但"填到我正在看的那一项"才符合预期。
        BD 模式保持按 AI 返回的编号匹配比赛（北单文件名自带编号，匹配可靠）。

        target_override：服务版直接指定目标（不读界面选中项）。

        Returns: ``{"applied", "skipped", "target_desc", "report"}``
        """
        if self.data_mode == 'bd':
            applied, skipped = self._apply_ai_bd(predictions)
            target_desc = "按 AI 返回编号匹配到的比赛"
        else:
            target = target_override if target_override is not None else self.selected_item_name()
            # 图片模式按 [胜负平, 胜负平, 比分, 比分] 组装槽位；HTML 模式保持原行为
            applied, skipped = self._apply_ai_jc(
                predictions, source_file=source_file,
                category_override=target,
                with_wdl=(self.data_mode == 'pic'))
            target_desc = f"*{target}*" if target else "(左侧未选中任何项)"

        report = self.report_apply_result(applied, skipped, target_desc, predictions)
        return {"applied": applied, "skipped": skipped,
                "target_desc": target_desc, "report": report}

    # ------------------------------------------------------------------
    # 导出 / 排序 / 汇总 JSON（S1b：写入类动作的纯逻辑）
    # ------------------------------------------------------------------

    def collect_all_export_ops(self):
        """汇总所有机构的导出写入操作（纯逻辑）

        对应桌面版「📤 一键导出」的 JC/HTML 分支（图片模式走逐分类导出，不在此列）。

        Returns: ``(all_ops, invalid_all, missing)``
            - ``all_ops``：``[(行, 列, [值])]`` 汇总后的写入操作
            - ``invalid_all``：加了机构前缀的无效数据描述（**仅值校验失败**）
            - ``missing``：映射表里匹配不到的机构名

        定位失败的编号记录在 ``self.last_locate_failures``（供服务端写进报告），
        **不混进 invalid_all**——桌面版的确认框默认是"否"，混进去会让整批被拒。
        """
        all_ops, invalid_all, missing = [], [], []
        locate_failures = []
        for item in self.left_items:
            ex_header = self.mapping.get(item)
            if not ex_header:
                missing.append(item)
                continue
            ops, invalid = collect_export_write_ops(
                self.get_info, self.data_storage, item, ex_header,
                False, self.excel_first_columns, logger,
                locate_failures=locate_failures)
            all_ops.extend(ops)
            invalid_all.extend(f"[{item}] {d}" for d in invalid)
        self.last_locate_failures = locate_failures
        return all_ops, invalid_all, missing

    def collect_category_export_ops(self, item, is_pic: bool = None):
        """单个机构 / 图片类别的导出写入操作（纯逻辑）

        图片模式走 ``is_pic=True``（跳过校验，允许中文胜负平直接写入）。

        Returns: ``(ops, invalid)``；定位失败的编号记录在 ``self.last_locate_failures``
        """
        if is_pic is None:
            is_pic = (self.data_mode == 'pic' and item in getattr(self, 'pic_categories', []))
        ex_header = self.pic_mapping[item] if is_pic else self.mapping[item]
        locate_failures = []
        ops, invalid = collect_export_write_ops(
            self.get_info, self.data_storage, item, ex_header,
            is_pic, self.excel_first_columns, logger,
            locate_failures=locate_failures)
        self.last_locate_failures = locate_failures
        return ops, invalid

    def collect_bd_export_infos(self):
        """收集北单导出条目并做"2 位数字"格式校验（纯逻辑）

        Returns: ``(infos, invalid)``
        """
        infos, invalid = [], []
        for label, info in self.bd_data_storage.items():
            scores = info.get("scores") or []
            if not scores or not info.get("code"):
                continue
            for i, score_set in enumerate(scores):
                for col_idx, s in enumerate(score_set[:4]):
                    s = str(s).strip()
                    if s and not re.fullmatch(r'\d{2}', s):
                        invalid.append(f"[{label}] 第{i+1}行第{col_idx+1}列: \"{s}\"")
            infos.append(info)
        return infos, invalid

    def collect_sort_ops(self):
        """统计各编号下比分/胜负平出现频率 → 生成排序写入操作（纯逻辑）

        沿用桌面版口径：**第 84 行起、按编号列纵向写入**。

        Returns: ``(write_ops, dict_counter)``
        """
        dict_counter = collect_sort_stats(self.data_storage, self.pic_categories, logger)
        write_ops = []
        for column, contents in dict_counter.items():
            try:
                _, column_location = self.get_info.get_location(header_num=column)
                write_ops.append((84, column_location, contents))
            except Exception:
                logger.exception(f"排序写入失败 - 列: {column}")
        return write_ops, dict_counter

    def export_json_file(self):
        """写出当日汇总 JSON（纯逻辑）

        - HTML / JC / 图片：``json/<日期>.json``（转置为 编号 → {机构: 槽位}）
        - 北单：``json/bd_<日期>.json``

        注意：这是**汇总 JSON②**，与每次 AI 提取自动留档的 ``json/ai/<日期>/``（JSON①）不是一回事。

        Returns: ``(ok, message)``；message 已写入日志，供宿主直接显示
        """
        try:
            if not os.path.exists("./json"):
                os.makedirs("./json")

            if self.data_mode == 'bd':
                json_path = f"./json/bd_{datetime.now().strftime('%Y-%m-%d')}.json"
                # BD 格式：{label: {code, home, away, scores}}
                export_data = {}
                for label, info in self.bd_data_storage.items():
                    if info.get("scores"):
                        export_data[label] = {
                            "code": info["code"],
                            "home": info["home"],
                            "away": info["away"],
                            "scores": info["scores"],
                        }
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=4)
                message = f"BD JSON 导出成功: {json_path} ({len(export_data)} 场比赛)"
                logger.info(message)
                self.is_dirty = False
                return True, message

            # JC/HTML/图片模式：转置为 code → category → scores
            new_json_data = {}
            for category, codes in self.data_storage.items():
                for code, scores in codes.items():
                    if code not in new_json_data:
                        new_json_data[code] = {}
                    new_json_data[code][category] = scores

            json_path = f"./json/{datetime.now().strftime('%Y-%m-%d')}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(new_json_data, f, ensure_ascii=False, indent=4)
            message = f"JSON文件导出成功: {json_path}"
            logger.info(message)
            self.is_dirty = False
            return True, message
        except Exception as e:
            logger.exception("JSON导出失败")
            return False, f"JSON导出失败：{str(e)}"
