import tkinter as tk
from tkinter import ttk

# 主窗口初始化
root = tk.Tk()
root.title("增强型数据编辑器")

# 配置数据（新增固定值列）
left_items = ['八神竞猜', '财神密码', '红龙']
top_data = [
    ['001', 'xxx', 'a1', 'b1', 'c1'],
    ['002', 'yyy', 'a2', 'b2', 'c2'],
    ['003', 'zzz', 'a3', 'b3', 'c3']
]

# 数据存储结构（包含固定值映射）
fixed_values = {row[0]: row[1] for row in top_data}  # 固定值全局映射
data_storage = {item: {row[0]: list(row[2:]) for row in top_data} for item in left_items}

# GUI组件
current_selection = tk.StringVar(value=left_items[0])
main_frame = ttk.Frame(root, padding=10)
main_frame.pack(fill='both', expand=True)

# 左侧选择面板
left_panel = ttk.Frame(main_frame)
left_panel.pack(side='left', fill='y')

# 动态表格容器
table_container = ttk.Frame(main_frame)
table_container.pack(side='left', fill='both', expand=True)

# 生成左侧选择按钮
for item in left_items:
    ttk.Radiobutton(left_panel, text=item, variable=current_selection, 
                   value=item, command=lambda: refresh_table()).pack(anchor='w', pady=2)

# 表格输入框存储
input_fields = []

def refresh_table():
    """刷新含固定值的表格"""
    global input_fields
    
    # 清空旧组件
    for widget in table_container.winfo_children():
        widget.destroy()
    input_fields.clear()

    # 获取当前数据
    selected = current_selection.get()
    current_data = data_storage[selected]

    # 创建表头
    headers = ['编号', '固定值', '字段A', '字段B', '字段C']
    for col, header in enumerate(headers):
        ttk.Label(table_container, text=header, borderwidth=1, 
                 relief='solid', width=10).grid(row=0, column=col)

    # 生成数据行
    for row_idx, (code, values) in enumerate(current_data.items(), start=1):
        # 编号列
        ttk.Label(table_container, text=code, width=10).grid(row=row_idx, column=0)
        
        # 固定值列（从全局映射获取）
        ttk.Label(table_container, text=fixed_values[code], width=10).grid(row=row_idx, column=1)
        
        # 可编辑字段
        row_entries = []
        for col_idx, value in enumerate(values, start=2):
            entry_var = tk.StringVar(value=value)
            ttk.Entry(table_container, textvariable=entry_var, width=10).grid(row=row_idx, column=col_idx)
            row_entries.append(entry_var)
        input_fields.append((code, row_entries))

def save_changes():
    """保存可编辑字段"""
    selected = current_selection.get()
    for code, entries in input_fields:
        data_storage[selected][code] = [e.get() for e in entries]

def export_data():
    """生成含固定值的导出数据"""
    save_changes()
    selected = current_selection.get()
    export_list = [selected]
    for code in data_storage[selected]:
        export_list.append({
            code: {
                'fixed': fixed_values[code],
                'fields': data_storage[selected][code]
            }
        })
    print("完整导出数据:", export_list)
    return export_list

# 功能按钮
button_row = ttk.Frame(root)
button_row.pack(pady=5)
ttk.Button(button_row, text="刷新", command=refresh_table).pack(side='left', padx=2)
ttk.Button(button_row, text="保存", command=save_changes).pack(side='left', padx=2)
ttk.Button(button_row, text="导出", command=export_data).pack(side='left', padx=2)

# 初始化界面
refresh_table()
root.mainloop()