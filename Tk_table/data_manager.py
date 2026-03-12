# data_manager.py
class DataManager:
    def __init__(self):
        self.left_items = ['八神竞猜', '财神密码', '红龙']
        self.base_data = [
            ['001', 'xxx', 'a1', 'b1', 'c1'],
            ['002', 'yyy', 'a2', 'b2', 'c2'],
            ['003', 'zzz', 'a3', 'b3', 'c3']
        ]
        
        self.fixed_values = {row[0]: row[1] for row in self.base_data}
        self.data_storage = self._init_data_storage()
    
    def _init_data_storage(self):
        """初始化数据结构"""
        return {
            item: {row[0]: list(row[2:]) for row in self.base_data}
            for item in self.left_items
        }
    
    def save_changes(self, current_item, input_fields):
        """保存当前条目数据"""
        if current_item in self.data_storage and input_fields:
            for code, entries in input_fields:
                self.data_storage[current_item][code] = [e.get() for e in entries]
    
    def get_export_data(self, current_item):
        """生成导出数据结构"""
        return [
            {code: {
                'fixed': self.fixed_values[code],
                'fields': values.copy()
            }} for code, values in self.data_storage[current_item].items()
        ]