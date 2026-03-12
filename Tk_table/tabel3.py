import tkinter as tk
from tkinter import ttk

class EnhancedDataEditor:
    def __init__(self, root=None, top_data: list = None, left_items: list = None):
        self.root = root if root else tk.Tk()
        self.root.title("增强型数据编辑器")

        self.left_items = ['八神竞猜', '财神密码', '红龙'] + [f"项目{i}" for i in range(4, 15)]  # 测试用15个项目
        self.top_data = [
            ['001', 'xxx', 'a1', 'b1', 'c1'],
            ['002', 'yyy', 'a2', 'b2', 'c2'],
            ['003', 'zzz', 'a3', 'b3']
        ]

        self.fixed_values = {row[0]: row[1] for row in self.top_data}
        self.data_storage = {item: {row[0]: list(row[2:]) for row in self.top_data} for item in self.left_items}
        self.current_selection = tk.StringVar(value=self.left_items[0])
        self.input_fields = []

        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill='both', expand=True)

        # 左侧面板容器（包含Canvas和滚动条）
        self.left_container = ttk.Frame(self.main_frame)
        self.left_container.pack(side='left', fill='y')

        # 创建带滚动条的Canvas
        self.left_canvas = tk.Canvas(self.left_container, width=120)  # 设置固定宽度
        self.scrollbar = ttk.Scrollbar(self.left_container, orient="vertical", command=self.left_canvas.yview)
        self.left_canvas.configure(yscrollcommand=self.scrollbar.set)

        # 放置Canvas和滚动条
        self.left_canvas.pack(side="left", fill="y", expand=False)
        self.scrollbar.pack(side="right", fill="y")

        # 创建内部Frame用于放置单选按钮
        self.left_inner_frame = ttk.Frame(self.left_canvas)
        self.left_canvas.create_window((0, 0), window=self.left_inner_frame, anchor="nw")

        # 绑定配置事件更新滚动区域
        self.left_inner_frame.bind("<Configure>", lambda e: self.left_canvas.configure(
            scrollregion=self.left_canvas.bbox("all")
        ))

        # 设置单选按钮的高度限制（每页显示10个）
        self.max_items_per_page = 10
        self._create_radio_buttons()

        self.table_container = ttk.Frame(self.main_frame)
        self.table_container.pack(side='left', fill='both', expand=True)

        self.button_row = ttk.Frame(self.root)
        self.button_row.pack(pady=5)
        ttk.Button(self.button_row, text="刷新", command=self.refresh_table).pack(side='left', padx=2)
        ttk.Button(self.button_row, text="保存", command=self.save_changes).pack(side='left', padx=2)
        ttk.Button(self.button_row, text="导出", command=self.export_data).pack(side='left', padx=2)

        self.refresh_table(self.current_selection.get())

    def _create_radio_buttons(self):
        """创建带滚动条的单选按钮列表"""
        for idx, item in enumerate(self.left_items):
            rb = ttk.Radiobutton(
                self.left_inner_frame,
                text=item,
                variable=self.current_selection,
                value=item,
                command=lambda i=item: self.refresh_table(i)
            )
            rb.grid(row=idx, column=0, sticky="w", pady=2)

        # 设置Canvas的显示高度（根据项目数量动态调整）
        item_count = min(len(self.left_items), self.max_items_per_page)
        self.left_canvas.config(height=item_count * 25)  # 假设每个项目高度25像素

    def refresh_table(self, selection=None):
        if selection is None:
            selection = self.current_selection.get()
        
        for widget in self.table_container.winfo_children():
            widget.destroy()
        self.input_fields.clear()

        current_data = self.data_storage[selection]

        headers = ['编号', '固定值', '字段A', '字段B', '字段C']
        for col, header in enumerate(headers):
            ttk.Label(self.table_container, text=header, borderwidth=1,
                     relief='solid', width=10).grid(row=0, column=col)

        for row_idx, (code, values) in enumerate(current_data.items(), start=1):
            ttk.Label(self.table_container, text=code, width=10).grid(row=row_idx, column=0)
            ttk.Label(self.table_container, text=self.fixed_values[code], width=10).grid(row=row_idx, column=1)
            row_entries = []
            for col_idx, value in enumerate(values, start=2):
                entry_var = tk.StringVar(value=value)
                ttk.Entry(self.table_container, textvariable=entry_var, width=10).grid(row=row_idx, column=col_idx)
                row_entries.append(entry_var)
            self.input_fields.append((code, row_entries))

    def save_changes(self):
        selection = self.current_selection.get()
        for code, entries in self.input_fields:
            self.data_storage[selection][code] = [e.get() for e in entries]

    def export_data(self):
        self.save_changes()
        selection = self.current_selection.get()
        export_list = {'category': selection, 'data': []}
        for code in self.data_storage[selection]:
            export_list['data'].append({
                code: {
                    'fixed': self.fixed_values[code],
                    'fields': self.data_storage[selection][code]
                }
            })
        print("完整导出数据:", export_list)
        return export_list
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    EnhancedDataEditor().run()