import tkinter as tk
from tkinter import ttk

class EnhancedDataEditor:
    def __init__(self, root = tk.Tk(), top_data:list =None, left_items:list =None):
        self.root = root
        self.root.title("增强型数据编辑器")

        self.left_items = ['八神竞猜', '财神密码', '红龙']
        self.top_data = [
            ['001', 'xxx', 'a1', 'b1', 'c1'],
            ['002', 'yyy', 'a2', 'b2', 'c2'],
            ['003', 'zzz', 'a3', 'b3', 'c3']
        ]

        self.fixed_values = {row[0]: row[1] for row in self.top_data}
        self.data_storage = {item: {row[0]: list(row[2:]) for row in self.top_data} for item in self.left_items}
        self.current_selection = tk.StringVar(value=self.left_items[0])
        self.input_fields = []

        self.main_frame = ttk.Frame(root, padding=10)
        self.main_frame.pack(fill='both', expand=True)

        self.left_panel = ttk.Frame(self.main_frame)
        self.left_panel.pack(side='left', fill='y')

        self.table_container = ttk.Frame(self.main_frame)
        self.table_container.pack(side='left', fill='both', expand=True)

        for item in self.left_items:
            ttk.Radiobutton(self.left_panel, text=item, variable=self.current_selection, 
                            value=item, command=lambda i=item: self.refresh_table(i)).pack(anchor='w', pady=2)

        self.button_row = ttk.Frame(root)
        self.button_row.pack(pady=5)
        ttk.Button(self.button_row, text="刷新", command=self.refresh_table).pack(side='left', padx=2)
        ttk.Button(self.button_row, text="保存", command=self.save_changes).pack(side='left', padx=2)
        ttk.Button(self.button_row, text="导出", command=self.export_data).pack(side='left', padx=2)

        self.refresh_table(self.current_selection.get())

    def refresh_table(self, selection=None):
        """
        刷新表格以显示所选项目的数据。

        :param selection: 要显示的项目名称，如果为None，则使用当前选中的项目。
        """
        # 如果没有提供选择，则获取当前选中的项目
        if selection is None:
            selection = self.current_selection.get()
        
        # 销毁表格容器中的所有子组件
        for widget in self.table_container.winfo_children():
            widget.destroy()
        # 清空输入字段列表
        self.input_fields.clear()

        # 获取当前选择的数据
        current_data = self.data_storage[selection]

        # 定义表格的表头
        headers = ['编号', '固定值', '字段A', '字段B', '字段C']
        # 遍历表头并创建标签显示
        for col, header in enumerate(headers):
            # 创建表头标签并设置样式
            ttk.Label(self.table_container, text=header, borderwidth=1, 
                      relief='solid', width=10).grid(row=0, column=col)

        # 遍历当前数据项
        for row_idx, (code, values) in enumerate(current_data.items(), start=1):
            # 显示编号
            ttk.Label(self.table_container, text=code, width=10).grid(row=row_idx, column=0)
            # 显示固定值
            ttk.Label(self.table_container, text=self.fixed_values[code], width=10).grid(row=row_idx, column=1)
            # 存储当前行的输入框变量
            row_entries = []
            # 遍历当前行的数据值
            for col_idx, value in enumerate(values, start=2):
                # 创建输入框变量并设置初始值
                entry_var = tk.StringVar(value=value)
                # 创建输入框并设置位置
                ttk.Entry(self.table_container, textvariable=entry_var, width=10).grid(row=row_idx, column=col_idx)
                # 将输入框变量添加到当前行的列表中
                row_entries.append(entry_var)
            # 将当前行的编号和输入框变量列表添加到输入字段列表中
            self.input_fields.append((code, row_entries))

    def save_changes(self):
        """
        保存用户在表格中所做的更改。

        此方法会获取当前选中的项目，并遍历输入字段列表，
        将每个输入框中的值更新到数据存储中对应项目的数据里。
        """
        # 获取当前选中的项目
        selection = self.current_selection.get()
        # 遍历输入字段列表，每个元素是一个元组 (code, entries)
        for code, entries in self.input_fields:
            # 将每个输入框中的值更新到数据存储中对应项目的数据里
            self.data_storage[selection][code] = [e.get() for e in entries]

    def export_data(self):
        """
        导出当前选中项目的数据。

        此方法会先保存用户所做的更改，然后将当前选中项目的数据整理成特定格式并导出。

        :return: 包含当前选中项目数据的字典，格式为 {'category': 项目名称, 'data': [代码数据字典列表]}
        """
        # 保存用户在表格中所做的更改
        self.save_changes()
        # 获取当前选中的项目
        selection = self.current_selection.get()
        # 初始化导出数据的字典，包含类别和数据列表
        export_list = {'category': selection, 'data': []}
        # 遍历当前选中项目的数据
        for code in self.data_storage[selection]:
            # 将每个代码对应的数据添加到导出列表中
            export_list['data'].append({
                code: {
                    # 固定值
                    'fixed': self.fixed_values[code],
                    # 字段值
                    'fields': self.data_storage[selection][code]
                }
            })
        # 打印完整的导出数据
        print("完整导出数据:", export_list)
        # 返回导出数据
        return export_list
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    # root = tk.Tk()
    # app = EnhancedDataEditor(root)
    # root.mainloop()
    EnhancedDataEditor().run()


