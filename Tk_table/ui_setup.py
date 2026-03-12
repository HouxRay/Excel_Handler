from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QScrollArea, QRadioButton, QButtonGroup, QSplitter, QPushButton,QWidget, QTableWidget, QHeaderView, QTableWidgetItem
from PyQt5.QtCore import Qt
from Tk_table.html_preview import HTMLPreview


class UISetup:
    def __init__(self, parent, excel_ops, html_preview):
        self.parent = parent
        self.excel_ops = excel_ops
        self.html_preview = html_preview

        self.table = None
        self.radio_group = None

    def setup_ui(self):
        main_splitter = QSplitter(Qt.Vertical)

        data_widget = self.setup_data_ui()
        main_splitter.addWidget(data_widget)

        html_widget = self.setup_html_ui()
        main_splitter.addWidget(html_widget)

        main_splitter.setSizes([600, 400])

        self.parent.setCentralWidget(main_splitter)

    def setup_data_ui(self):
        data_widget = QWidget()
        layout = QHBoxLayout(data_widget)

        left_scroll = QScrollArea()
        left_scroll.setFixedWidth(150)
        left_scroll.setWidgetResizable(True)

        self.radio_group = QButtonGroup()
        radio_container = QWidget()
        radio_layout = QVBoxLayout(radio_container)
        radio_layout.setAlignment(Qt.AlignTop)

        for idx, item in enumerate(self.excel_ops.left_items):
            radio = QRadioButton(item)
            self.radio_group.addButton(radio, idx)
            radio_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)

        left_scroll.setWidget(radio_container)
        layout.addWidget(left_scroll)

        right_layout = QVBoxLayout()

        self.table = self.excel_ops.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['编号', '队伍', '比分1', '比分2', '比分3', '比分4'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.create_buttons(btn_layout)
        right_layout.addLayout(btn_layout)

        layout.addLayout(right_layout)

        self.radio_group.buttonClicked.connect(self.refresh_table)
        self.refresh_table()

        return data_widget

    def setup_html_ui(self):
        html_widget = QWidget()
        layout = QVBoxLayout(html_widget)

        html_btn_layout = QHBoxLayout()
        open_btn = QPushButton('打开HTML文件')
        open_btn.clicked.connect(self.html_preview.open_html)
        refresh_btn = QPushButton('刷新预览')
        refresh_btn.clicked.connect(lambda: self.html_preview.web_view.reload())
        html_btn_layout.addWidget(open_btn)
        html_btn_layout.addWidget(refresh_btn)
        html_btn_layout.addStretch()

        layout.addLayout(html_btn_layout)

        layout.addWidget(self.html_preview.web_view)

        return html_widget

    def create_buttons(self, layout):
        buttons = [
            ('刷新数据', self.refresh_table),
            ('保存修改', self.excel_ops.save_changes),
            ('导出Excel', self.excel_ops.export_data),
            ('清空表格', self.clear_table)
        ]

        for text, handler in buttons:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            layout.addWidget(btn)
        layout.addStretch()

    def refresh_table(self):
        selected = self.excel_ops.left_items[0]  # 假设这里获取的是选中的项目
        data = self.excel_ops.data_storage[selected]

        self.table.setRowCount(len(data))
        for row, (code, values) in enumerate(data.items()):
            self.table.setItem(row, 0, QTableWidgetItem(code))
            self.table.setItem(row, 1, QTableWidgetItem(self.excel_ops.fixed_values[code]))
            for col, value in enumerate(values, start=2):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def clear_table(self):
        for row in range(self.table.rowCount()):
            for col in range(2, 6):
                if item := self.table.item(row, col):
                    item.setText("")
