# ExcelHander 乱序表头支持修复方案

## 问题分析

当前代码在 `Excel_Info.py` 的 `get_location` 方法中，使用以下公式计算列位置：
```python
column_location = (int(excel_first_num)-1) * 4 + 2
```

这个公式假设：
1. 表头数字是连续的（001,002,003,004...）
2. 每个表头数字对应4列数据
3. 数据从第2列开始

当表头数字乱序时（如001,003,002,005...），这个公式会计算出错误的列位置。

## 解决方案

需要修改代码，使其能够：
1. 动态查找表头数字在Excel中的实际列位置
2. 根据实际列位置计算数据写入位置
3. 保持向后兼容性

## 具体修改步骤

### 1. 修改 `Excel_Info.py` 中的 `get_location` 方法

需要添加一个方法来查找表头数字对应的实际列位置，而不是通过公式计算。

### 2. 修改 `Excel_Info.py` 中的 `__init__` 方法

需要缓存表头数字到列位置的映射关系。

### 3. 修改 `table_qt.py` 中的相关调用

确保所有调用 `get_location` 的地方都使用新的逻辑。

## 实现细节

### 步骤1：在 `Excel_Info.py` 中添加表头数字映射

```python
def __init__(self, file_path: str, excel_path: str):
    # ... 现有代码 ...
    self.header_num_to_column = {}  # 新增：表头数字到列位置的映射
    self._build_header_num_mapping()  # 新增：构建映射关系

def _build_header_num_mapping(self):
    """构建表头数字到列位置的映射"""
    import re
    ws = self.wb.active
    
    # 假设表头在第一行
    for col in range(1, ws.max_column + 1):
        cell_value = ws.cell(row=1, column=col).value
        if cell_value and isinstance(cell_value, str):
            # 提取3位数字
            match = re.search(r'(\d{3})', cell_value)
            if match:
                num = match.group(1)
                self.header_num_to_column[num] = col
```

### 步骤2：修改 `get_location` 方法

```python
def get_location(self, mapping_value: str = None, excel_first_num: str = None, excel_first_columns: Union[str, List[str]] = None) -> int:
    """
    获取写入信息的坐标 
    """     
    try:  
        if mapping_value and excel_first_num and excel_first_columns:
            line_location = excel_first_columns[mapping_value]
            
            # 新逻辑：查找表头数字对应的实际列位置
            if excel_first_num in self.header_num_to_column:
                header_col = self.header_num_to_column[excel_first_num]
                # 数据列在表头列的右侧，每4列一组
                column_location = header_col + 1  # 假设数据在表头右侧第1列开始
            else:
                # 回退到旧逻辑（保持兼容性）
                column_location = (int(excel_first_num)-1) * 4 + 2
                
            return line_location, column_location
            
        elif excel_first_num:
            # 新逻辑：查找表头数字对应的实际列位置
            if excel_first_num in self.header_num_to_column:
                header_col = self.header_num_to_column[excel_first_num]
                column_location = header_col + 1  # 假设数据在表头右侧第1列开始
            else:
                # 回退到旧逻辑（保持兼容性）
                column_location = (int(excel_first_num)-1) * 4 + 2
                
            return None, column_location
            
    except Exception as e:
        # 捕获并处理可能出现的异常
        print(f"An error occurred while getting location: {e}")
        pass
```

### 步骤3：测试修改

需要创建测试用例来验证：
1. 连续表头数字（001,002,003,004）仍然正常工作
2. 乱序表头数字（001,003,002,005）能够正确写入
3. 缺失表头数字的情况能够正确处理

## 风险与注意事项

1. **向后兼容性**：必须确保现有功能不受影响
2. **性能影响**：构建映射关系会增加初始化时间，但只执行一次
3. **错误处理**：需要处理表头数字不存在的情况
4. **Excel格式假设**：假设表头在第一行，每个表头数字对应4列数据

## 备选方案

如果上述方案太复杂，可以考虑：
1. 修改Excel模板，使表头数字按顺序排列
2. 在写入前对数据进行排序
3. 使用更简单的映射表配置文件

## 下一步

1. 备份当前代码
2. 实施上述修改
3. 进行充分测试
4. 验证所有功能正常