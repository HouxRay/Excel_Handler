# Excel Handler

一个用于处理Excel文件的Python应用程序，支持数据导入、导出和格式化。

## 功能特点

- Excel文件导入和导出
- 数据格式化和处理
- 支持乱序表头数字（如001,003,002,005）
- 图形用户界面（基于PyQt5）

## 项目结构

```
ExcelHander/
├── src/                    # 源代码目录
│   ├── Excel_Info.py      # Excel信息处理类
│   └── Excel_Writer.py    # Excel写入类
├── window/                # 窗口界面
│   └── table_qt.py        # 主界面
├── mapping/               # 映射文件
│   └── mapping_data.txt   # 数据映射
└── test/                  # 测试文件
```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

1. 运行主程序：
```bash
python window/table_qt.py
```

2. 在界面中选择Excel文件和HTML文件
3. 点击导入按钮开始处理数据

## 最近修复

- 修复了`get_location`方法的参数顺序问题
- 增强了错误处理和日志记录
- 改进了表头数字映射逻辑

## 许可证

MIT License