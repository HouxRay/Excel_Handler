# controller.py
from data_manager import DataManager
from view import MainView

class AppController:
    def __init__(self, root):
        self.model = DataManager()
        self.view = MainView(root, self)
        
        # 初始化显示
        self.refresh_table()
    
    def get_left_items(self):
        """获取左侧菜单项"""
        return self.model.left_items
    
    def on_selection_change(self):
        """处理选项变更事件"""
        self.refresh_table()
    
    def refresh_table(self):
        """刷新表格数据"""
        current_item = self.view.get_current_selection()
        current_data = self.model.data_storage[current_item]
        self.view.refresh_table(current_data, self.model.fixed_values)
    
    def export_data(self):
        """处理数据导出"""
        current_item = self.view.get_current_selection()
        self.model.save_changes(current_item, self.view.get_input_fields())
        return self.model.get_export_data(current_item)
    
    def save_data(self):
        """显式保存操作"""
        current_item = self.view.get_current_selection()
        input_fields = self.view.get_input_fields()
        self.model.save_changes(current_item, input_fields)
        print(f"手动保存完成：{current_item} 数据状态：{self.model.data_storage[current_item]}")