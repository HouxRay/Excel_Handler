from PyQt5.QtWidgets import QMessageBox
from src.Excel_Info import GetWriteInfo
from src.Excel_Writer import ExcelWriter


class ExcelOperations:
    def __init__(self, top_data, left_items):
        self.get_info = GetWriteInfo("src\\2025-03-03-竞彩", "src\sample.xlsx")
        self.writer = ExcelWriter("src\\2025-03-03-竞彩", "src\sample.xlsx")
        self.file_name, self.excel_name = self.get_info.get_file_and_excel_info()
        self.mapping = self.get_info.get_mapping()
        self.header_bases = self.get_info.get_header_bases()

        self.initialize_data(top_data, left_items)

    def initialize_data(self, top_data, left_items):
        self.left_items = left_items or ['八神竞猜', '财神密码', '红龙'] + [f"项目{i}" for i in range(4, 15)]
        self.top_data = top_data or [
            ['001', 'xxx', 'a1', 'b1', 'c1', 'd1'],
            ['002', 'yyy', 'a2', 'b2', 'c2', 'd2'],
            ['003', 'zzz', 'a3', 'b3', 'c3', "d2"]
        ]

        self.fixed_values = {row[0]: row[1] for row in self.top_data}
        self.data_storage = {
            item: {row[0]: list(row[2:]) for row in self.top_data}
            for item in self.left_items
        }

    def save_changes(self):
        selected = self.left_items[0]  # 假设这里获取的是选中的项目
        for row in range(self.table.rowCount()):
            code = self.table.item(row, 0).text()
            new_values = [self.table.item(row, col).text() for col in range(2, 6)]
            self.data_storage[selected][code] = new_values

    def export_data(self):
        self.save_changes()
        selected = self.left_items[0]  # 假设这里获取的是选中的项目

        export_data = {
            'category': selected,
            'data': [{
                code: {'fixed': self.fixed_values[code], 'fields': values}
            } for code, values in self.data_storage[selected].items()]
        }

        try:
            for item in export_data['data']:
                code = list(item.keys())[0]
                values = item[code]['fields']
                try:
                    line, col = self.get_info.get_location(export_data['category'], code, self.excel_name)
                    self.writer.write_info(line, col, value=values)
                except Exception as e:
                    print(e)
                    continue
                print("导出完成")
            return export_data
        except Exception as e:
            print(e)
            pass
