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
