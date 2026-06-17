# 项目更新日志

> 本文档汇总了项目开发过程中的关键更新记录。

---

---

## 2026-06-17 — 设置界面优化：映射文件独立标签页；BD文件外部测试 (v2.4.0 → v2.4.1)

### 功能优化

**文件：** [window/settings_dialog.py](window/settings_dialog.py)

- **映射文件编辑独立标签页**：将"名称映射文件 (mapping_data.txt)"从"映射设置"移出，新建独立的"名称映射"标签页，方便用户操作
- 对话框高度从 520 调整为 560，为新标签页留出空间

### 外部测试

**文件：** [AI/test_bd.py](AI/test_bd.py)（新建）

- 创建北单（BD）文件解析与兼容性测试脚本（外部测试模块，不修改现有代码）
- 测试覆盖：A数量.html 汇总文件解析（10 场比赛，76 条预测，21 家预测机构）
- 测试覆盖：每个北单N.html 详细文件解析
- 测试覆盖：架构兼容性（编号格式、选项格式、Excel 表头匹配、data_storage 结构）
- **测试结论：BD 文件与当前架构不兼容**
  - 编号 `北单N` 格式 vs 现有 `3位数字` 编号系统
  - 选项含 `主队-0.5 胜` 让球盘格式 vs 标准胜平负简写
  - 文件按比赛组织 vs 按预测机构组织冲突

### 版本号

- `v2.4.0` → `v2.4.1`（功能优化）

---

## 2026-06-16 — Bug修复：打开窗口崩溃、JSON排序统计遗漏；功能升级：映射文件在线编辑 (v2.3.0 → v2.4.0)

### Bug 修复

**文件：** [window/table_qt.py](window/table_qt.py)

**1. 第二次点击"打开"时程序静默退出 (CRITICAL)**
- **根因：** `NewWindow.closeEvent` 中 `deleteLater()` 与 `WA_DeleteOnClose` 冲突，导致 `QWebEngineView` 被双重删除（父析构 + deleteLater 队列），引发 QtWebEngine 进程段错误
- **修复：**
  - HTML 模式：删除 `closeEvent` 中的 `self.web_view.deleteLater()`，子 widget 由 `WA_DeleteOnClose` 触发的父析构函数自动清理
  - 图片模式：`_show_pic_txt_dialog` 创建的 `QDialog` 添加 `WA_DeleteOnClose`，防止关闭后 C++ 对象残留

**2. JSON排序只统计最后一次写入 (CRITICAL)**
- **根因：** 三个问题叠加：
  - JSON 格式检测条件无法区分新旧格式（`{code→category} vs {category→code}`），旧格式数据被静默丢弃
  - 条件导入 `if category in self.data_storage and code in ...` 丢弃当前 `data_storage` 中不存在的 code
  - `sort()` 不调用 `save_changes()`，编辑未保存时只统计旧数据
- **修复：**
  - 格式检测改用 `re.match(r'\d{3}', first_key)` 判断顶层 key 是否为编号
  - 条件导入放宽为 `category in data_storage` 时直接写入，不在时新建分类
  - `sort()` 开头添加 `self.save_changes()` 确保编辑内容先写回

### 功能升级

**文件：** [window/settings_dialog.py](window/settings_dialog.py)

- **映射文件在线编辑：** "映射设置"标签页新增"名称映射文件 (mapping_data.txt)"编辑表格
  - 支持添加行、删除选中行、清空表格
  - "应用"时自动将编辑内容写回 `mapping_data.txt` 文件
  - 通过 `_reload_with_new_paths()` 自动重新加载，无需重启程序

### 版本号

- `v2.3.0` → `v2.4.0`（功能升级 + Bug 修复）

---

## 2026-05-18 — Python 3.10 环境升级、类型注解现代化 (v2.2.1 → v2.3.0)

### 环境升级

- **Python 3.8 → 3.10**：新建 conda 环境 `qt310`
- 所有依赖重新安装（PyQt5、PyQtWebEngine、openpyxl、pypinyin、html2text、requests）

### 语法升级

**修改文件：** [src/Excel_Info.py](src/Excel_Info.py)、[src/Excel_Writer.py](src/Excel_Writer.py)、[src/File_Reader.py](src/File_Reader.py)、[src/Name_Matcher.py](src/Name_Matcher.py)、[ai/ai_extractor.py](ai/ai_extractor.py)

- `Union[X, Y]` → `X | Y`（PEP 604 联合类型）
- `List[X]` → `list[X]`、`Dict[X, Y]` → `dict[X, Y]`（PEP 585 内建泛型）
- 移除所有 `from typing import Union, List, Dict` 导入

### Bug 修复

**文件：** [window/settings_dialog.py](window/settings_dialog.py)

- `_read_table_to_dict` 中 `.strip()` 会删除空格键的键值 `" "`，导致空格映射在保存时丢失；改为 `.rstrip('\n\r')` 仅去除换行

### 版本号

- `v2.2.1` → `v2.3.0`（环境升级）

---

## 2026-05-15 — Pic模式txt文件创建、映射关系可视化配置 (v2.1.3 → v2.2.0)

### 1. Pic模式 — 新建/编辑txt文件

**文件：** [window/table_qt.py](window/table_qt.py) — `on_open_clicked`、`_show_pic_txt_dialog`（新增）

- **问题：** 图片模式下点击"打开"时，若txt文件不存在则直接报错，用户需手动创建文件
- **修复：**
  - 新增 `_show_pic_txt_dialog()` 方法：展示可编辑的 QTextEdit 对话框
  - txt 存在时：加载现有内容到编辑框，允许修改并保存
  - txt 不存在时：显示空白编辑框，点击"保存"自动创建文件
  - 对话框提供"保存"和"取消"按钮，取消不产生文件

### 2. 映射关系可视化配置

**文件：** [src/mapping_manager.py](src/mapping_manager.py)（新建）、[window/settings_dialog.py](window/settings_dialog.py)、[src/Excel_Writer.py](src/Excel_Writer.py)、[window/table_qt.py](window/table_qt.py)

- **问题：** MATCH_DICT（代码→中文）和键盘映射（空格/反引号→0）硬编码在源码中，无法查看或自定义
- **修复：**
  - 新建 `src/mapping_manager.py`：统一管理映射的加载、保存、重置逻辑
  - 映射通过 QSettings 持久化（JSON 格式），键为 `mappings/match_dict` 和 `mappings/keyboard`
  - SettingsDialog 重组为 QTabWidget 双标签页："路径设置" + "映射设置"
  - 映射设置页包含两个可编辑表格：MATCH_DICT 和键盘映射
  - 每个表格支持添加行、删除选中行、"重置默认值"恢复默认
  - `ExcelWriter` 新增 `reload_match_dict()` 函数，从 QSettings 加载自定义映射
  - `SpaceToZeroDelegate` 改为从 mapping_manager 读取键盘映射，不再硬编码
  - `save_changes()` 和 `_on_fill_from_txt()` 中 `.replace()` 统一使用 `apply_keyboard_mappings()`
  - 设置"应用"后自动同步 MATCH_DICT 和键盘映射到运行时

### 3. 版本号更新

- `v2.1.3` → `v2.2.0`（功能升级）

---

## 2026-05-14 (修复) — 写入线程死锁修复、HTML窗口内存泄漏修复 (v2.1.2 → v2.1.3)

### 1. 多线程写入死锁修复

**文件：** [window/table_qt.py](window/table_qt.py) — `_run_write_worker`、`_on_thread_finished`

- **问题：** 连续多次快速写入后程序卡死在"正在后台写入"，旧线程的 `finished` lambda 会覆盖新线程的 `worker_thread` 引用，导致线程状态错乱、资源泄漏，最终死锁
- **修复：**
  - 移除 `lambda: setattr(self, 'worker_thread', None)`，改用 `_on_thread_finished()` 方法
  - 新增 `_on_thread_finished` 方法：安全清理 `worker` 和 `worker_thread`
  - `_run_write_worker` 启动前调用 `worker_thread.wait(3000)` 等待旧线程完全退出
  - 防止 `worker_thread` 引用被旧线程的延迟信号意外清空

### 2. HTML 查看器内存泄漏修复

**文件：** [window/table_qt.py](window/table_qt.py) — `NewWindow` 类

- **问题：** 每次打开 HTML 窗口都会新增一个 `QtWebEngineProcess.exe` 进程（10-100MB），关闭窗口后进程不释放，持续累积
- **根因：** `QDialog.close()` 仅隐藏窗口，`QWebEngineView` 的渲染进程未被释放
- **修复：**
  - `NewWindow.__init__` 添加 `setAttribute(Qt.WA_DeleteOnClose)` 确保关闭时自动删除窗口
  - 新增 `closeEvent`：显式调用 `web_view.setPage(None)` + `stop()` + `deleteLater()` 释放渲染进程
  - `on_open_clicked` 关闭旧窗口后立即设置 `self.current_window = None`

### 3. 版本号更新

- `v2.1.2` → `v2.1.3`（Bug 修复）

---

## 2026-05-14 — HTML星期高亮、设置对话框、清空按钮、刷新颜色变更 (v2.0.5 → v2.1.0)

### 1. HTML星期高亮

**文件：** [window/table_qt.py](window/table_qt.py) — `NewWindow` 类

- **新增：** 工具栏 + QComboBox 下拉菜单，默认自动检测北京时区 (UTC+8) 当前星期
- **新增：** JavaScript 通过 TreeWalker 遍历文本节点，将包含目标星期（周一~周日）的文字用黄色背景+红色加粗样式高亮
- **交互：** 用户可通过下拉菜单手动切换高亮星期

### 2. 设置对话框

**文件：** [window/settings_dialog.py](window/settings_dialog.py)（新建）、[window/table_qt_2.py](window/table_qt_2.py)、[window/table_conbine.py](window/table_conbine.py)、[window/table_qt.py](window/table_qt.py)、[src/Excel_Info.py](src/Excel_Info.py)

- **新增：** `SettingsDialog` 类，提供四个路径配置项：映射文件路径、HTML文件夹路径、Excel文件路径、JSON文件路径
- **新增：** 使用 `QSettings` (INI 格式 `config.ini`) 实现路径持久化存储
- **新增：** 主窗口添加 "设置" 蓝色按钮，点击弹出设置对话框
- **改进：** `PathSelector` 启动时自动从 `config.ini` 预填路径
- **改进：** `run()` 在选择路径后自动保存到 `config.ini`
- **改进：** `GetWriteInfo` 新增 `mapping_path` 参数，使映射文件路径可配置
- **交互：** 点击"应用"立即保存并重新加载数据；点击"取消"如有修改则提示"是否保存更改?"

### 3. 清空按钮 + 刷新按钮颜色变更

**文件：** [window/table_qt.py](window/table_qt.py)

- **新增：** "清空" 蓝色按钮，清空当前页面表格列2-5（比分列）的显示内容，不影响 `data_storage`
- **变更：** "刷新" 按钮从蓝色改为橙色 (#FF9800)

### 4. 版本号更新

- `v2.0.5` → `v2.1.0`（功能升级）

---

## 2026-05-13 — 键盘输入优化、数据源切换、版本号

### 1. 空格/反引号代替 0 输入

**文件：** [window/table_qt.py](window/table_qt.py)

- **问题：** 无小键盘用户输入 "0" 时手部别扭
- **修复：** 新增 `CustomTableWidget(QTableWidget)` 子类，重写 `keyPressEvent`：编辑时按空格键或反引号键自动插入 "0"，其他按键正常

### 2. HTML/图片 数据源切换

**文件：** [window/table_qt.py](window/table_qt.py)、[src/Excel_Handler.py](src/Excel_Handler.py)

- **问题：** 部分数据源来自 txt 文件而非 HTML，无法在软件中直接查看和输入，且汉字数据被 MATCH_DICT 验证拦截；Excel_Handler 连续空行阈值过小导致跳过数据
- **修复：**
  - 左侧面板新增 "HTML" / "图片" 两个切换按钮
  - 图片模式使用 `mapping/mapping_pic.txt` 作为映射（与 `mapping_data.txt` 同格式：`excel行名：类别名`）
  - "打开"按钮在图片模式读取并显示 `<类别>.txt` 文本内容
  - 新增橙色 "📥 填入数据" 按钮，在图片模式下从 txt 自动解析并填入表格对应编号行
  - `export_data()` 对图片模式类别跳过 MATCH_DICT 验证，允许汉字直接写入
  - `read_first_column` 空行容忍阈值从 2 提高到 50，解决图片类别在 104-117 行被跳过的 bug
  - `File_Reader._is_valid_file` 添加 `.html` 扩展名过滤，防止 `.txt` 文件混入 HTML 文件列表
  - `sort()` 排除图片模式类别（`pic_categories`），仅统计 HTML 模式数据

### 3. 版本号显示

**文件：** [window/table_qt.py](window/table_qt.py)

- **问题：** 无版本标识
- **修复：** 在日志框下方添加灰色小字 `v2.0.5`

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
