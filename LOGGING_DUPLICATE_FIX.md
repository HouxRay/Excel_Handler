# 日志重复输出问题修复

## 问题描述
用户报告在终端中看到重复的日志输出，例如：
```
2026-03-12 20:10:37,294 - INFO - 开始写入 *胆大成*
2026-03-12 20:10:37,294 - INFO - 开始写入 *胆大成*
2026-03-12 20:10:40,366 - INFO - *胆大成* 写入完成
2026-03-12 20:10:40,366 - INFO - *胆大成* 写入完成
```

## 问题分析
经过代码分析，发现问题出现在以下位置：

1. **多个模块都配置了日志记录器**：`table_qt.py`、`table_qt_2.py`、`table_qt_test.py` 都定义了 `setup_logger()` 函数
2. **每个模块都创建了自己的日志记录器**：使用 `logging.getLogger(__name__)` 创建独立的记录器
3. **每个记录器都添加了处理器**：都添加了文件处理器和控制台处理器
4. **日志消息传播**：当模块相互导入时，日志消息可能会被多个记录器处理

## 根本原因
Python的logging模块中，日志记录器有一个层次结构。当子记录器记录消息时，消息会传播到父记录器（除非设置了 `propagate=False`）。

在ExcelHander项目中：
- `table_qt.py` 导入了 `table_qt_2.py`
- 两个模块都创建了自己的日志记录器
- 两个记录器都添加了处理器
- 当 `table_qt.py` 记录日志时，消息可能被两个记录器处理，导致重复输出

## 修复方案

### 1. 防止重复添加处理器
修改 `setup_logger()` 函数，检查记录器是否已经有处理器，避免重复添加：

```python
# 防止重复添加处理器
if not logger.handlers:
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
```

### 2. 禁用日志传播
设置 `logger.propagate = False`，防止日志消息传播到父记录器：

```python
# 禁用日志传播，防止重复输出
logger.propagate = False
```

### 3. 防止重复添加GUI处理器
对于GUI日志处理器，检查是否已经添加了相同的处理器：

```python
# 如果提供了文本窗口，添加GUI处理器
if text_widget:
    # 检查是否已经添加了GUI处理器
    gui_handler_exists = any(
        isinstance(h, QTextEditLogger) and h.text_widget == text_widget 
        for h in logger.handlers
    )
    if not gui_handler_exists:
        gui_handler = QTextEditLogger(text_widget)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)
```

## 修复的文件
1. `/mnt/d/ExcelHander/window/table_qt.py` - 主窗口日志配置
2. `/mnt/d/ExcelHander/window/table_qt_2.py` - 路径选择器日志配置
3. `/mnt/d/ExcelHander/window/table_qt_test.py` - 测试窗口日志配置

## 修复验证
修复后，日志输出应该不再重复：
```
2026-03-12 20:10:37,294 - INFO - 开始写入 *胆大成*
2026-03-12 20:10:40,366 - INFO - *胆大成* 写入完成
```

## 注意事项
1. 设置 `propagate=False` 后，日志消息不会传播到父记录器
2. 如果需要全局的日志配置，建议使用根记录器 (`logging.getLogger()`) 而不是模块特定的记录器
3. 在多模块应用中，最好统一日志配置，避免每个模块都配置自己的记录器

## 替代方案
如果问题仍然存在，可以考虑以下替代方案：

1. **统一日志配置**：创建一个专门的日志配置模块，所有其他模块都从该模块获取记录器
2. **使用根记录器**：所有模块都使用 `logging.getLogger()` 获取根记录器
3. **环境变量控制**：使用环境变量控制日志级别和输出目标

## 测试建议
1. 运行应用程序，检查日志输出是否重复
2. 测试不同的日志级别（INFO、DEBUG、WARNING）
3. 验证日志文件是否正确记录（不重复）
4. 测试GUI日志输出是否正常工作