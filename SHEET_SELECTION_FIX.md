# Sheet选择功能修复文档

## 问题描述
用户报告了一个sheet选择功能的问题：当Excel文件退出时保存在sheet3，用户通过界面选择sheet2后，数据仍然被写入到sheet3而不是sheet2。

## 问题分析
经过代码分析，发现问题出现在以下位置：

1. **ExcelWriter类**：在构造函数中总是使用`self.workbook.active`来获取工作表
   ```python
   # 原代码
   self.ws = self.workbook.active
   ```
   这导致无论用户选择哪个sheet，总是写入Excel文件中最后保存的活动sheet。

2. **主窗口调用**：创建ExcelWriter时没有传递用户选择的sheet名称

## 修复方案

### 1. 修改ExcelWriter类 (`src/Excel_Writer.py`)
- 修改构造函数，添加`sheet_name`参数
- 根据`sheet_name`参数选择工作表：
  - 如果指定了`sheet_name`且工作表存在，使用该工作表
  - 如果指定了`sheet_name`但工作表不存在，创建新工作表
  - 如果没有指定`sheet_name`，使用活动工作表（保持向后兼容）

```python
# 修改后的构造函数
def __init__(self, excel_path: str, sheet_name: str = None):
    self.excel_path = excel_path
    self.workbook = load_workbook(self.excel_path)
    
    # 根据sheet_name参数选择工作表
    if sheet_name:
        # 检查工作表是否存在
        if sheet_name in self.workbook.sheetnames:
            self.ws = self.workbook[sheet_name]
        else:
            # 如果工作表不存在，创建它
            self.ws = self.workbook.create_sheet(title=sheet_name)
    else:
        # 如果没有指定sheet_name，使用活动工作表
        self.ws = self.workbook.active
```

### 2. 修改主窗口 (`window/table_qt.py`)
- 修改EnhancedDataEditor构造函数，接收`sheet_name`参数
- 在创建ExcelWriter时传递`sheet_name`参数

```python
# 修改后的ExcelWriter创建
self.writer = ExcelWriter(excel_path, sheet_name)
```

### 3. 修改程序入口点 (`window/table_conbine.py`)
- 修改EnhancedDataEditor的调用，传递`sheet_name`参数

```python
# 修改后的主窗口创建
main_window = EnhancedDataEditor(excel_path=excel_path,
                                 file_path=folder_path,
                                 json_path=json_path,
                                 sheet_name=sheet_name)
```

## 修复验证

### 测试用例
1. **场景**：Excel退出时保存在sheet3，用户选择sheet2
   - 路径选择器返回`sheet_name='Sheet2'`
   - EnhancedDataEditor创建`ExcelWriter(excel_path, 'Sheet2')`
   - ExcelWriter使用`workbook['Sheet2']`而不是`workbook.active`
   - **结果**：数据写入Sheet2而不是Sheet3 ✓

2. **场景**：用户不选择sheet（保持默认）
   - 路径选择器返回`sheet_name=None`
   - EnhancedDataEditor创建`ExcelWriter(excel_path, None)`
   - ExcelWriter使用`workbook.active`
   - **结果**：数据写入活动工作表（向后兼容）✓

3. **场景**：用户选择不存在的sheet
   - 路径选择器返回`sheet_name='NewSheet'`
   - EnhancedDataEditor创建`ExcelWriter(excel_path, 'NewSheet')`
   - ExcelWriter创建新工作表`NewSheet`
   - **结果**：数据写入新创建的工作表 ✓

## 影响范围
- 仅影响使用ExcelWriter写入Excel文件的功能
- 不影响读取和显示数据的功能
- 保持向后兼容：不传递sheet_name时使用原行为

## 文件修改清单
1. `/mnt/d/ExcelHander/src/Excel_Writer.py` - ExcelWriter类构造函数
2. `/mnt/d/ExcelHander/window/table_qt.py` - 主窗口类
3. `/mnt/d/ExcelHander/window/table_conbine.py` - 程序入口点

## 注意事项
1. 旧版本代码（Tk_table目录）未修改，因为主程序使用window目录
2. 测试代码中的ExcelWriter调用未修改，不影响主程序功能
3. 如果未来需要添加sheet选择到其他功能，需要相应修改ExcelWriter的调用

## 测试建议
1. 使用不同的Excel文件测试sheet选择功能
2. 测试选择已存在的sheet和创建新sheet
3. 测试不选择sheet时的默认行为
4. 验证数据正确写入到选择的sheet