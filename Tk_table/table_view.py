import tkinter as tk
from tkinter import ttk


class MainView():
    def __init__(self):
        self.root = tk.Tk()
        self.left_item = ['八神竞猜', '财神密码', '红龙']
        self.top_items = [
                        ['001', 'xxx', 'a1', 'b1', 'c1'],
                        ['002', 'yyy', 'a2', 'b2', 'c2'],
                        ['003', 'zzz', 'a3', 'b3', 'c3']]
        
        # 表格输入框存储
        self.input_fields = []
        
    def data_structure(self) -> None:
        self.fixed_values = {row[0]: row[1] for row in self.top_items}  # 固定值全局映射
        self.data_storage = {item: {row[0]: list(row[2:]) for row in self.top_items} for item in self.left_item}
    
    def create_table(self) -> None:
        self.current_selection = tk.StringVar(value=self.top_items[0])
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill='both', expand=True)

        # 左侧选择面板
        self.left_panel = ttk.Frame(self.main_frame)
        self.left_panel.pack(side='left', fill='y')

        # 动态表格容器
        self.table_container = ttk.Frame(self.main_frame)
        self.table_container.pack(side='left', fill='both', expand=True)

        # 生成左侧选择按钮
        for item in self.left_item:
            ttk.Radiobutton(self.left_panel, text=item, variable=self.current_selection, 
                   value=item, command=lambda: self.refresh_table()).pack(anchor='w', pady=2)


    def refresh_table(self):
        """刷新含固定值的表格"""

        # 清空旧组件
        for widget in self.table_container.winfo_children():
            widget.destroy()
        self.input_fields.clear()

        # 获取当前数据
        selected = self.current_selection.get()
        current_data = self.data_storage[selected]

        # 创建表头
        headers = ['编号', '固定值', '字段A', '字段B', '字段C']
        for col, header in enumerate(headers):
            ttk.Label(self.table_container, text=header, borderwidth=1, 
                     relief='solid', width=10).grid(row=0, column=col)

        # 生成数据行
        for row_idx, (code, values) in enumerate(current_data.items(), start=1):
            # 编号列
            ttk.Label(self.table_container, text=code, width=10).grid(row=row_idx, column=0)

            # 固定值列（从全局映射获取）
            ttk.Label(self.table_container, text=self.fixed_values[code], width=10).grid(row=row_idx, column=1)

            # 可编辑字段
            row_entries = []
            for col_idx, value in enumerate(values, start=2):
                entry_var = tk.StringVar(value=value)
                ttk.Entry(self.table_container, textvariable=entry_var, width=10).grid(row=row_idx, column=col_idx)
                row_entries.append(entry_var)
            self.input_fields.append((code, row_entries))

    
    def save_changes(self):
        """保存可编辑字段"""
        selected = self.current_selection.get()
        for code, entries in self.input_fields:
            self.data_storage[selected][code] = [e.get() for e in entries]

    def export_data(self):
        """生成含固定值的导出数据"""
        self.save_changes()
        selected = self.current_selection.get()
        export_list = [selected]
        for code in self.data_storage[selected]:
            export_list.append({
                code: {
                    'fixed': self.fixed_values[code],
                    'fields': self.data_storage[selected][code]
                }
            })
        print("完整导出数据:", export_list)
        return export_list
    
    def bottom(self):
        button_row = ttk.Frame(self.root)
        button_row.pack(pady=5)
        ttk.Button(button_row, text="刷新", command=self.refresh_table).pack(side='left', padx=2)
        ttk.Button(button_row, text="保存", command=self.save_changes).pack(side='left', padx=2)
        ttk.Button(button_row, text="导出", command=self.export_data).pack(side='left', padx=2)

    def init_table(self):
        # 初始化界面
        self.refresh_table()
        self.root.mainloop()
    
    def run(self):
        self.data_structure()
        self.create_table()
        self.bottom()
        self.init_table()

if __name__ == '__main__':
    MainView().run()