# view.py
import tkinter as tk
from tkinter import ttk

class MainView:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.input_fields = []
        
        self._setup_main_window()
        self._create_widgets()
    
    def _setup_main_window(self):
        """窗口基础设置"""
        self.root.title("模块化数据编辑器")
        self.root.minsize(600, 400)
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill='both', expand=True)
    
    def _create_widgets(self):
        """创建界面组件"""
        self._create_left_panel()
        self._create_table_container()
        self._create_buttons()
    
    def _create_left_panel(self):
        """左侧选择面板"""
        self.left_panel = ttk.Frame(self.main_frame, width=120)
        self.left_panel.pack(side='left', fill='y')
        
        self.selection_var = tk.StringVar()
        for item in self.controller.get_left_items():
            rb = ttk.Radiobutton(
                self.left_panel,
                text=item,
                variable=self.selection_var,
                value=item,
                command=self.controller.on_selection_change
            )
            rb.pack(anchor='w', pady=5, padx=10)
        self.selection_var.set(self.controller.get_left_items()[0])
    
    def _create_table_container(self):
        """表格显示区域"""
        self.table_container = ttk.Frame(self.main_frame)
        self.table_container.pack(side='left', fill='both', expand=True)
    
    def _create_buttons(self):
        """功能按钮区"""
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill='x', pady=5)
        
        ttk.Button(button_frame, text="刷新", 
                 command=self.controller.refresh_table).pack(side='left', padx=2)
        ttk.Button(button_frame, text="导出", 
                 command=self.controller.export_data).pack(side='left', padx=2)
        ttk.Button(button_frame, text="保存", 
                command=self.controller.save_data).pack(side='left', padx=2)
    
    def refresh_table(self, current_data, fixed_values):
        """刷新表格显示"""
        # 清空旧组件
        for widget in self.table_container.winfo_children():
            widget.destroy()
        self.input_fields.clear()
        
        # 创建表头
        headers = ['编号', '固定值', '字段A', '字段B', '字段C']
        for col, header in enumerate(headers):
            ttk.Label(self.table_container, text=header, borderwidth=1, 
                     relief='solid', width=10).grid(row=0, column=col)
        
        # 填充数据行
        for row_idx, (code, values) in enumerate(current_data.items(), start=1):
            ttk.Label(self.table_container, text=code, width=10).grid(
                row=row_idx, column=0)
            ttk.Label(self.table_container, text=fixed_values[code], 
                     width=10).grid(row=row_idx, column=1)
            
            row_entries = []
            for col_idx, value in enumerate(values, start=2):
                entry_var = tk.StringVar(value=value)
                ttk.Entry(self.table_container, textvariable=entry_var, 
                         width=10).grid(row=row_idx, column=col_idx)
                row_entries.append(entry_var)
            self.input_fields.append((code, row_entries))

    def save_data(self):
        """显式保存数据"""
        current_item = self.view.get_current_selection()
        self.model.save_changes(
            current_item, 
            self.view.get_input_fields()
        )
        print(f"手动保存完成：{current_item}")
    
    def get_current_selection(self):
        """获取当前选中项"""
        return self.selection_var.get()
    
    def get_input_fields(self):
        """获取输入字段引用"""
        return self.input_fields