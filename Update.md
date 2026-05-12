# 项目更新日志

> 本文档汇总了项目开发过程中的关键更新记录。

---

## 2025-03-13

### 修复排序功能错误

修复排序功能中的 bug（对应 commit `d2a4ff0`）。

---

## 2025-03-12 — 多项修复与功能增强

当日进行了多项重要更新，以下按时间线整理。

### 1. 界面布局全面优化

**文件：** [window/table_qt.py](window/table_qt.py)

- "重新选择路径"按钮移到左上角独立显示，使用绿色主题醒目样式
- 所有主功能按钮重新设计，添加图标前缀（📂 🔄 💾 📤 📊 📝）
- 现代化 CSS 样式：圆角、悬停高亮、按压反馈、加粗字体
- 布局分为两行：顶部独立按钮行 + 主功能按钮行

### 2. Excel 表头格式兼容修复

**文件：** [src/Excel_Handler.py](src/Excel_Handler.py) — `_is_valid_base` 方法

- **问题：** 当 Excel 表头因合并单元格呈现为 `[序号, "队伍A队伍B", "", ""]` 格式时，旧验证逻辑判定无效导致数据被过滤
- **修复：** 放宽第二个文字列的验证条件，允许为空
- **效果：** 同时支持标准格式 `[序号, 队伍A, 队伍B, 空]` 和合并单元格格式

### 3. Sheet 选择功能上线

**文件：** 涉及多个文件

新增 Excel Sheet 选择功能，用户可在打开文件时指定要操作的 Sheet：
- `table_qt_2.py`：路径选择器新增 Sheet 下拉框，自动加载 Excel 所有 sheet 名称
- `GetWriteInfo`、`ExcelHandler`、`NameMatcher`、`EnhancedDataEditor` 均新增 `sheet_name` 参数
- 向后兼容：不指定 sheet 时默认使用活动 sheet

### 4. Sheet 选择写入修复

**文件：** [src/Excel_Writer.py](src/Excel_Writer.py)、[window/table_qt.py](window/table_qt.py)

- **问题：** `ExcelWriter` 始终使用 `workbook.active` 写入，无视用户选择的 sheet
  - 例：文件退出时保存在 Sheet3，用户选择 Sheet2，数据仍写入 Sheet3
- **修复：** `ExcelWriter.__init__` 新增 `sheet_name` 参数，根据用户选择定位工作表
  - 指定 sheet 存在 → 使用该 sheet
  - 指定 sheet 不存在 → 创建新 sheet
  - 未指定 → 使用活动 sheet（向后兼容）

### 5. 日志重复输出修复

**文件：** [window/table_qt.py](window/table_qt.py)、[window/table_qt_2.py](window/table_qt_2.py)

- **问题：** 多个模块各自配置日志记录器，导致日志消息被多个处理器处理，输出重复
- **修复：**
  - `setup_logger()` 中检查 `logger.handlers` 防止处理器重复添加
  - 设置 `logger.propagate = False` 禁止日志向父记录器传播
  - GUI 日志处理器添加前检查是否已存在相同实例

---

## 2026-05-12 — 多线程改造与多项优化

### 1. 写入/排序多线程化（不阻塞UI）

**文件：** [src/Excel_Writer.py](src/Excel_Writer.py)、[src/worker.py](src/worker.py)（新建）、[window/table_qt.py](window/table_qt.py)

- **问题：** 导出和排序操作在主线程执行 Excel 写入，`workbook.save()` 每次调用都序列化整个工作簿，导致界面卡顿
- **方案：** 采用二阶段架构：
  1. **主线程阶段：** 收集所有写入操作，获取行列坐标，不执行实际 I/O
  2. **后台线程阶段：** 通过 `ExcelWriteWorker(QObject)` 在工作线程执行写入，最后统一 `save()`
- **新增 [src/worker.py](src/worker.py)：** `ExcelWriteWorker` 类，通过 `pyqtSignal` 与主线程通信（`finished`、`progress`）
- **新增方法：**
  - `ExcelWriter.batch_write_cell()` — 静默单格写入
  - `ExcelWriter.batch_write_list()` — 静默横向批量写入
  - `ExcelWriter.batch_write_dict()` — 静默纵向批量写入
  - `ExcelWriter.save()` — 显式保存
  - `ExcelWriter.validate_value()` — 纯验证方法（无UI），可在主线程预先验证
- **新增 `_run_write_worker()` 机制：** 防止重复启动工作线程，显示 `QProgressDialog` 进度条

### 2. 绿色按钮误触确认

**文件：** [window/table_qt.py](window/table_qt.py) — `reload_paths()` 方法

- **问题：** "重新选择路径"绿色按钮点击后直接关闭主窗口，丢弃所有未保存修改，无确认提示，且容易误触
- **修复：**
  - 添加 `QMessageBox.question` 确认对话框，默认选"否"
  - 添加 `is_dirty` 标记追踪未保存修改，对话框中提示"有未保存的修改"
  - `save_changes()` 和导出成功后自动更新 dirty 标记

### 3. 重新选择路径时关闭HTML窗口

**文件：** [window/table_qt.py](window/table_qt.py) — `reload_paths()` 方法

- **问题：** 点击重新选择路径后，HTML 预览窗口未被关闭，成为孤儿窗口
- **修复：** 在 `self.close()` 之前检查并关闭 `self.current_window`

### 4. JSON 格式改进（跨sheet数据复用）

**文件：** [window/table_qt.py](window/table_qt.py) — `export_json()` 和 JSON 导入逻辑

- **问题：** 旧 JSON 格式 `{category: {code: [scores]}}` 强依赖 category 名称（HTML 文件名），切换 sheet 后无法匹配
- **修复：**
  - **新导出格式：** `{code: {category: [scores]}}`（按比赛编号组织）
  - **导入兼容：** 自动检测新旧格式，新格式按 code 匹配导入，旧格式使用原有 `update()` 逻辑
  - 导入时只匹配当前 `data_storage` 中存在的 category+code 组合，不引入无关数据
