# Doro统治世界 — Excel数据分析工具

一个基于 **PyQt5** 的桌面应用程序，用于读取、编辑和导出竞彩体育数据分析结果。通过选择 HTML 数据源和 Excel 模板，自动匹配数据并写入指定位置，支持多 Sheet 选择、数据排序、HTML 预览等功能。

## 项目结构

```
├── main.py                      # 程序启动入口
├── window/                      # GUI 界面模块
│   ├── table_conbine.py         # 流程编排：路径选择 → 主窗口
│   ├── table_qt.py              # 主窗口：数据编辑、导出、排序、HTML 预览
│   ├── table_qt_2.py            # 路径选择器对话框
│   ├── settings_dialog.py       # 设置对话框（路径持久化配置）
│   └── table_qt_test.py         # 测试版主窗口
├── src/                         # 核心业务逻辑
│   ├── Excel_Handler.py         # Excel 文件读取（表头、首列数据）
│   ├── Excel_Info.py            # 数据协调层：读取、映射、定位计算
│   ├── Excel_Writer.py          # Excel 数据写入（含验证、多线程写入）
│   ├── Excel_Writer_text.py     # 旧版文本式 Excel 写入器
│   ├── File_Reader.py           # 文件系统读取（HTML 文件遍历、文件名提取）
│   ├── Name_Matcher.py          # 名称匹配（文件名 ↔ Excel 行映射）
│   ├── worker.py                # 后台工作线程（Excel 写入不阻塞 UI）
│   ├── Data_viewer_test.py      # Tkinter 版测试数据查看器
│   └── Name_Matcher_test1.py    # 名称匹配测试脚本
├── mapping/                     # 映射配置文件
│   ├── mapping_data.txt         # HTML 模式：文件名 ↔ Excel 列名映射
│   └── mapping_pic.txt          # 图片模式：类别名映射
├── assets/
│   └── pic.ico                  # 应用图标
├── json/                        # 数据导出目录（JSON 格式备份）
├── logs/                        # 日志文件目录
└── config.ini                   # 持久化配置文件（启动自动生成）
```

## 功能特性

| 功能 | 说明 |
|------|------|
| **路径选择** | 选择 HTML 文件夹、Excel 文件、JSON 文件、Excel Sheet，支持持久化记忆 |
| **数据编辑** | 左侧分类导航 + 右侧表格编辑，支持 HTML/图片两种数据源模式切换 |
| **键盘优化** | 编辑时按空格或反引号自动转为 "0"，方便无小键盘用户 |
| **保存/导出** | 编辑后保存到内存，点击导出写入 Excel（后台线程，不阻塞 UI） |
| **HTML 预览** | 内嵌 WebEngine，支持星期高亮（自动检测北京时区 + 手动切换） |
| **图片模式** | 从 txt 文件读取数据，支持汉字直接写入，配有自动填入按钮 |
| **数据排序** | 统计各编号下比分出现频率，写入 Excel 指定区域（后台线程） |
| **JSON 备份** | 将当前数据导出为 JSON 文件（按编号组织），支持二次导入和格式兼容 |
| **设置对话框** | 运行时修改映射/HTML/Excel/JSON 路径，应用立即生效，取消可保存 |
| **路径持久化** | 通过 `config.ini` 记忆路径和 Sheet，下次启动自动预填 |
| **清空按钮** | 一键清空当前页面所有输入及已保存数据，带二次确认 |
| **日志系统** | 文件日志 + GUI 日志框，防止重复输出 |
| **路径重载** | 不重启应用即可切换数据源，带未保存确认，自动保存到配置 |

## 环境要求

- Python 3.8+
- PyQt5
- openpyxl
- PyQtWebEngine
- pypinyin

## 快速开始

```bash
# 安装依赖
pip install PyQt5 PyQtWebEngine openpyxl pypinyin

# 运行
python main.py
```

## 使用流程

1. **启动程序** → 弹出路径选择对话框
2. **选择数据源**：
   - 文件夹：包含 HTML 文件的目录（各分析师的推荐页面）
   - Excel 文件：目标工作簿（包含赛事编号、队伍、比分等列）
   - JSON 文件：可选，用于导入之前导出的数据继续编辑
   - Sheet：选择 Excel 中的目标工作表
3. **编辑数据**：
   - 左侧单选按钮切换分析师分类
   - 右侧表格显示该分类下的赛事数据
   - 比分单元格可直接编辑
4. **操作按钮**（按颜色分为三行）：
   - 🟢 **绿色行**：🔄 重新选择路径 | 🗑️ 清空（带二次确认）
   - 🟠 **橙色行**：📥 填入数据（图片模式）| 🔄 刷新 | ⚙️ 设置
   - 🔵 **蓝色行**：📂 打开 | 💾 保存 | 📤 导出 | 📊 排序 | 📝 写入JSON

## 核心模块说明

### Excel 读取与解析

[src/Excel_Handler.py](src/Excel_Handler.py) 负责读取 Excel 文件：
- **首列数据**：从第二行开始读取，获取每行对应的分类名称
- **表头解析**：按 4 列一组解析表头（编号、队伍A、队伍B、空），支持合并单元格格式

### 名称匹配

[src/Name_Matcher.py](src/Name_Matcher.py) 将 HTML 文件名与 Excel 首列数据进行匹配：
- 支持包含（contains）、前缀（startswith）、后缀（endswith）匹配模式
- `create_mapping_v2` 使用预定义的映射文件将文件名映射到 Excel 表头

### 坐标计算

[src/Excel_Info.py](src/Excel_Info.py) 的 `get_location` 方法计算数据写入位置：
- 支持乱序表头数字（如 001, 003, 002）
- 自动构建表头数字到列的映射

### 数据写入

[src/Excel_Writer.py](src/Excel_Writer.py) 写入时进行数据验证：
- 支持 2 位数字比分
- 支持预定义的胜负符号映射（s→胜, ss→胜胜, f→负, p→平等）
- 写入前校验，无效数据弹窗确认
- 多线程写入：主线程收集操作 + 后台线程执行 I/O（不阻塞 UI）

### 后台工作线程

[src/worker.py](src/worker.py) 使用 `QThread` + `pyqtSignal` 实现：
- `ExcelWriteWorker` 在工作线程执行 Excel 写入和保存
- 进度信号实时反馈，支持 `QProgressDialog` 进度条
- 防止重复启动，确保线程安全

### 设置与持久化

[window/settings_dialog.py](window/settings_dialog.py) 提供运行时配置：
- 映射文件路径 / HTML 文件夹 / Excel 文件 / JSON 文件 / Sheet 选择
- 通过 `QSettings` (INI 格式) 存储到 `config.ini`
- 启动时自动预填，修改后"应用"立即生效，"取消"提示保存

## 当前版本

**v2.1.3**（2026-05-14）

## 依赖项

```
PyQt5          — GUI 框架
PyQtWebEngine  — HTML 预览
openpyxl       — Excel 读写
pypinyin       — 文件名拼音排序
```

## 许可

MIT License
