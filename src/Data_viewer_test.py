import tkinter as tk
from tkinter import ttk

class EditableTreeview(ttk.Treeview):
    def __init__(self, master, editable_columns, **kwargs):
        super().__init__(master, **kwargs)
        self.editable_columns = editable_columns
        self.bind("<Button-1>", self._on_single_click)  # 改为单击事件
        self.edit_entry = None
        self._click_timer = None  # 用于处理双击冲突

    def _on_single_click(self, event):
        """处理单击事件"""
        # 取消之前的计时器
        if self._click_timer:
            self.master.after_cancel(self._click_timer)
            self._click_timer = None
        
        # 延迟处理避免与双击冲突
        self._click_timer = self.master.after(300, self._process_click, event)

    def _process_click(self, event):
        """实际处理单击逻辑"""
        region = self.identify_region(event.x, event.y)
        if region == "cell":
            column = self.identify_column(event.x)
            if column in self.editable_columns:
                self._start_edit(event)


    def _start_edit(self, event):
        """启动编辑"""
        # 获取选中位置
        row_id = self.identify_row(event.y)
        column = self.identify_column(event.x)
        
        # 获取单元格坐标
        x, y, width, height = self.bbox(row_id, column)
        
        # 获取当前值
        current_value = self.item(row_id, "values")[int(column[1:])-1]
        
        # 创建输入框
        self.edit_entry = ttk.Entry(self)
        self.edit_entry.place(x=x, y=y, width=width, height=height)
        self.edit_entry.insert(0, current_value)
        self.edit_entry.focus_set()
        
        # 绑定事件
        self.edit_entry.bind("<Return>", lambda e: self._finish_edit(row_id, column))
        self.edit_entry.bind("<FocusOut>", lambda e: self._finish_edit(row_id, column))

    def _finish_edit(self, row_id, column):
        """完成编辑"""
        if self.edit_entry:
            new_value = self.edit_entry.get()
            col_index = int(column[1:]) - 1  # 列索引从0开始
            current_values = list(self.item(row_id, "values"))
            current_values[col_index] = new_value
            self.item(row_id, values=current_values)
            self.edit_entry.destroy()
            self.edit_entry = None



class DataViewer:
    def __init__(self, master, selection_callback=None):
        """
        带选择回调的数据浏览器
        :param master: 父容器
        :param selection_callback: 选择回调函数（接收选中文本参数）
        """
        self.master = master
        self.selection_callback = selection_callback
        master.title("增强版数据浏览器")
        master.geometry("800x600")
        
        # 创建主容器
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 初始化界面
        self._create_left_panel()
        self._create_top_panel()
        self._create_data_panel()

    def _create_left_panel(self):
        """左侧垂直列表"""
        left_frame = ttk.Frame(self.main_frame, width=150)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # 树形列表组件
        self.left_tree = ttk.Treeview(left_frame, show="tree", selectmode="browse")
        self.left_tree.pack(fill=tk.BOTH, expand=True)
        
        # 填充示例数据
        items = ['八神竞猜', '财神密码', '红龙']
        for item in items:
            self.left_tree.insert("", tk.END, text=item)
        
        # 绑定选择事件
        self.left_tree.bind("<<TreeviewSelect>>", self._on_left_select)

    def _create_top_panel(self):
        """顶部可编辑列表"""
        top_frame = ttk.Frame(self.main_frame, height=120)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        # 创建可编辑表格（编号列不可编辑）
        self.top_tree = EditableTreeview(
            top_frame,
            editable_columns=("#2", "#3", "#4"),  # 允许编辑参数列
            columns=("col1", "col2", "col3", "col4"),
            show="headings"
        )
        self.top_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 配置列（保持不变）
        columns = ["编号", "参数1", "参数2", "状态"]
        for idx, col in enumerate(columns):
            self.top_tree.heading(f"#{(idx+1)}", text=col)
            self.top_tree.column(f"#{(idx+1)}", width=100)
        
        # 填充示例数据（编号列保持不可编辑）
        sample_data = [
            ["001", "数据A", "参数X", None],
            ["002", "数据B", "参数Y", None],
            ["003", "数据C", "参数Z", "进行中"]
        ]
        for row in sample_data:
            self.top_tree.insert("", tk.END, values=row)
        
        # 水平滚动条
        h_scroll = ttk.Scrollbar(top_frame, orient=tk.HORIZONTAL, command=self.top_tree.xview)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.top_tree.configure(xscrollcommand=h_scroll.set)

    def _create_data_panel(self):
        """主数据面板（添加状态显示）"""
        data_frame = ttk.Frame(self.main_frame)
        data_frame.pack(fill=tk.BOTH, expand=True)
        
        # 添加状态显示标签
        self.status_bar = ttk.Label(data_frame, text="当前选择：无")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 数据表格
        self.data_table = ttk.Treeview(data_frame, columns=("时间", "数值", "状态"), show="headings")
        self.data_table.pack(fill=tk.BOTH, expand=True)
        
        # 配置列
        for col in ["时间", "数值", "状态"]:
            self.data_table.heading(col, text=col)
            self.data_table.column(col, width=100)
        
        # 垂直滚动条
        v_scroll = ttk.Scrollbar(data_frame, orient=tk.VERTICAL, command=self.data_table.yview)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.data_table.configure(yscrollcommand=v_scroll.set)

    def _on_left_select(self, event):
        """处理左侧选择事件"""
        selected = self.left_tree.selection()
        if selected:
            item_text = self.left_tree.item(selected, "text")
            self.status_bar.config(text=f"当前选择：{item_text}")
            
            # 执行回调函数
            if self.selection_callback:
                try:
                    self.selection_callback(item_text)
                except Exception as e:
                    print(f"回调函数执行失败：{str(e)}")

# 使用示例
if __name__ == "__main__":
    root = tk.Tk()
    
    def handle_selection(selected_text):
        """自定义回调函数示例"""
        print(f"[回调] 接收到选择：{selected_text}")
        # 这里可以添加业务逻辑，例如更新其他组件内容
    app = DataViewer(root, selection_callback=handle_selection)

      # 添加测试按钮显示当前数据
    def show_data():
        for child in app.top_tree.get_children():
            print(app.top_tree.item(child, "values"))
    
    ttk.Button(root, text="显示数据", command=show_data).pack()
    
    root.mainloop()