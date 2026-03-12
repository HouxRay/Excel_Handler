# Excel Sheet选择功能说明

## 功能概述
现在ExcelHander应用支持选择Excel文件中的特定sheet进行处理，解决了之前只能使用活动sheet的限制。

## 修改内容

### 1. 路径选择器增强
- **新增Sheet选择下拉框**：在选择Excel文件后，自动加载所有sheet名称
- **界面布局调整**：增加了sheet选择行，窗口高度适当增加
- **路径验证**：现在需要同时验证文件夹、Excel文件和sheet选择

### 2. 核心类修改
#### GetWriteInfo类
- 构造函数新增`sheet_name`参数
- 支持指定sheet名称，如果sheet不存在则使用活动sheet并显示警告

#### ExcelHandler类
- 构造函数新增`sheet_name`参数
- 支持读取指定sheet的数据

#### NameMatcher类
- 构造函数新增`sheet_name`参数
- 在匹配时使用指定sheet的数据

#### EnhancedDataEditor类
- 构造函数新增`sheet_name`参数
- 初始化时传递sheet_name给GetWriteInfo

### 3. 主窗口修改
#### reload_paths函数
- 接收路径选择器返回的sheet_name
- 验证sheet_name的有效性
- 创建新窗口时传递sheet_name参数

## 使用流程

### 新用户流程
1. 启动应用
2. 点击"🔄 重新选择路径"按钮
3. 选择文件夹路径
4. 选择Excel文件（自动加载sheet列表）
5. 选择JSON文件
6. 从下拉框中选择要处理的sheet
7. 点击"确认"按钮
8. 应用加载指定sheet的数据

### 现有用户兼容性
- 如果不指定sheet_name，默认使用活动sheet（向后兼容）
- 如果指定的sheet不存在，使用活动sheet并显示警告

## 技术实现细节

### 1. Sheet名称加载
```python
# 使用openpyxl的read_only模式快速加载sheet名称
wb = load_workbook(filename=excel_file, read_only=True)
sheet_names = wb.sheetnames
```

### 2. Sheet选择验证
```python
# 在路径选择器中验证
if not selected_sheet:
    QMessageBox.warning(self, "警告", "请选择Excel sheet！")
    return
```

### 3. Sheet切换逻辑
```python
# 在GetWriteInfo中处理sheet选择
if sheet_name and sheet_name in self.wb.sheetnames:
    self.ws = self.wb[sheet_name]
else:
    self.ws = self.wb.active
```

## 错误处理

### 1. Excel文件读取失败
- 显示错误消息框
- 禁用sheet选择下拉框

### 2. Sheet不存在
- 显示警告信息
- 自动切换到活动sheet
- 继续正常处理

### 3. 路径无效
- 验证所有路径（文件夹、Excel文件、JSON文件）
- 验证sheet选择
- 显示具体的错误信息

## 界面变化

### 路径选择器界面
```
┌─────────────────────────────────────────┐
│ 文件夹路径: [_______________] [浏览...] │
│ Excel文件路径: [_____________] [浏览...] │
│ JSON文件路径: [______________] [浏览...] │
│ 选择Sheet: [下拉选择框▼]                │
│                    [确认]                │
└─────────────────────────────────────────┘
```

### 主界面按钮
- "🔄 重新选择路径"按钮已移到左上角
- 所有按钮添加了图标和现代化样式
- 按钮分为两行布局，提高可用性

## 测试验证

所有修改已通过以下测试：
- ✅ 路径选择器导入和属性检查
- ✅ GetWriteInfo支持sheet_name参数
- ✅ ExcelHandler支持sheet_name参数
- ✅ NameMatcher支持sheet_name参数
- ✅ EnhancedDataEditor支持sheet_name参数
- ✅ reload_paths函数正确处理sheet_name

## 注意事项

1. **性能考虑**：使用`read_only=True`模式加载sheet名称，避免加载整个文件
2. **内存使用**：处理大型Excel文件时，建议使用`data_only=True`避免公式计算
3. **向后兼容**：现有代码如果不指定sheet_name，行为不变
4. **错误恢复**：sheet选择失败时自动回退到活动sheet

## 未来扩展

1. **多sheet支持**：同时处理多个sheet
2. **sheet预览**：在选择前预览sheet内容
3. **自动检测**：根据内容自动推荐合适的sheet
4. **批量处理**：批量处理多个Excel文件的相同sheet