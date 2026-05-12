# Doro统治世界 — Excel数据分析工具

一个基于 **PyQt5** 的桌面应用程序，用于读取、编辑和导出竞彩体育数据分析结果。通过选择 HTML 数据源和 Excel 模板，自动匹配数据并写入指定位置，支持多 Sheet 选择、数据排序、HTML 预览等功能。

## 项目结构

```
├── main.py                      # 程序启动入口
├── window/                      # GUI 界面模块
│   ├── table_conbine.py         # 流程编排：路径选择 → 主窗口
│   ├── table_qt.py              # 主窗口：数据编辑、导出、排序、HTML 预览
│   ├── table_qt_2.py            # 路径选择器对话框
│   └── table_qt_test.py         # 测试版主窗口
├── src/                         # 核心业务逻辑
│   ├── Excel_Handler.py         # Excel 文件读取（表头、首列数据）
│   ├── Excel_Info.py            # 数据协调层：读取、映射、定位计算
│   ├── Excel_Writer.py          # Excel 数据写入（含验证）
│   ├── Excel_Writer_text.py     # 旧版文本式 Excel 写入器
│   ├── File_Reader.py           # 文件系统读取（HTML 文件遍历、文件名提取）
│   ├── Name_Matcher.py          # 名称匹配（文件名 ↔ Excel 行映射）
│   ├── Data_viewer_test.py      # Tkinter 版测试数据查看器
│   └── Name_Matcher_test1.py    # 名称匹配测试脚本
├── assets/
│   └── pic.ico                  # 应用图标
├── json/                        # 数据导出目录（JSON 格式备份）
└── src/2025-03-03-竞彩/          # HTML 示例数据
```

## 功能特性

| 功能 | 说明 |
|------|------|
| **路径选择** | 选择 HTML 文件夹、Excel 文件、JSON 文件、Excel Sheet |
| **数据编辑** | 左侧分类导航 + 右侧表格编辑，支持多分类数据切换 |
| **保存/导出** | 编辑后保存到内存，点击导出写入 Excel |
| **HTML 预览** | 内嵌 WebEngine，可预览对应分类的 HTML 页面 |
| **数据排序** | 统计各编号下比分出现频率，写入 Excel 指定区域 |
| **JSON 备份** | 将当前数据导出为 JSON 文件，支持二次导入 |
| **日志系统** | 文件日志 + GUI 日志框，防止重复输出 |
| **路径重载** | 不重启应用即可切换数据源 |

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
4. **操作按钮**：
   - 📂 打开：使用 WebEngine 预览当前分类的 HTML 页面
   - 🔄 刷新：重新加载表格数据
   - 💾 保存：将当前修改保存到内存
   - 📤 导出：将数据写入 Excel 文件
   - 📊 排序：统计比分频率并写入
   - 📝 写入 JSON：导出当前数据为 JSON 备份

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

## 依赖项

```
PyQt5          — GUI 框架
PyQtWebEngine  — HTML 预览
openpyxl       — Excel 读写
pypinyin       — 文件名拼音排序
```

## 许可

MIT License
