import sys
import re
import os
import glob
import json
from datetime import datetime

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QScrollArea, QRadioButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QPushButton, QButtonGroup, QDialog, QLabel, QMessageBox,
                             QTextEdit, QProgressDialog, QStyledItemDelegate, QFileDialog)
from PyQt5.QtCore import Qt, QThread, QEvent, QSettings, QTimer
from PyQt5.QtGui import QIcon

from src.Excel_Info import GetWriteInfo
from src.Excel_Writer import ExcelWriter, reload_match_dict
from src.mapping_manager import apply_keyboard_mappings, get_keyboard_mappings
from src.BD_Handler import parse_bd_detail, load_bd_config, export_bd_data, sort_bd_data
from src.data_loader import load_pic_config, load_json_to_storage, load_bd_json, reinitialize_data
from src.exporter import collect_export_write_ops, collect_sort_stats
from src.log_setup import logger, setup_logger, QTextEditLogger
from src.zip_handler import ensure_extracted
from src import ai_handler, ai_config, ai_storage
from window.html_viewer import NewWindow
from window.settings_dialog import SettingsDialog
from window.ai_preview_dialog import AiPreviewDialog
from window.ai_history_dialog import AiHistoryDialog





class SpaceToZeroDelegate(QStyledItemDelegate):
    """编辑代理：空格/反引号强制替换为0，并支持自定义 text() 映射"""
    def __init__(self, parent=None, mappings=None):
        super().__init__(parent)
        if mappings is None:
            mappings = get_keyboard_mappings()
        self._mappings = mappings

    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        editor.installEventFilter(self)
        return editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            key = event.key()
            # 空格 / 反引号强行替换为 0（key() 优先，不依赖 text()）
            if key == Qt.Key_Space or key == Qt.Key_QuoteLeft:
                obj.insert("0")
                return True
            # 也支持 text() 驱动的自定义映射（如用户添加 "/" → "1"）
            text = event.text()
            if text and text in self._mappings:
                obj.insert(self._mappings[text])
                return True
        return super().eventFilter(obj, event)

    def setModelData(self, editor, model, index):
        """提交编辑前应用键盘映射替换"""
        text = editor.text()
        text = apply_keyboard_mappings(text, self._mappings)
        model.setData(index, text)


class EnhancedDataEditor(QMainWindow):
    def __init__(self, top_data:list = None,
                 left_items:list = None,
                 excel_name:list = None,
                 excel_path:str = None,
                 file_path:str = None,
                 json_path:str = None,
                 sheet_name:str = None,
                 bd_file_path:str = None,
                 bd_excel_path:str = None,
                 bd_sheet_name:str = None,
                 bd_json_path:str = None,
                 html_source_path:str = None,
                 bd_source_path:str = None):
        """
        top_data：队伍数据
        left_items：html文件名称
        excel_name：excel文件名称
        excel_path：excel文件路径
        file_path：html文件路径
        json_path：json文件路径（用于二次整理时引入新数据）
        sheet_name：Excel sheet名称
        bd_file_path：北单HTML文件夹路径
        bd_excel_path：BD专属Excel文件路径
        bd_sheet_name：BD专属Sheet名称
        bd_json_path：BD专属JSON文件路径
        """
        super().__init__()
        self.setWindowTitle("Doro统治世界")
        # 恢复上次关闭时的窗口位置和大小
        geom = QSettings("config.ini", QSettings.IniFormat).value("window/geometry")
        if geom:
            self.restoreGeometry(geom)
        else:
            self.setGeometry(300, 300, 800, 600)
        
        # 设置窗口图标
        try:
            icon_path = "assets/pic.ico"  # 图标文件路径
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            else:
                logger.warning(f"图标文件未找到: {icon_path}")
        except Exception as e:
            logger.exception("设置窗口图标时发生错误")
        
        if top_data is None or left_items is None or excel_name is None:
            if file_path:
                self.get_info = GetWriteInfo(file_path, excel_path, sheet_name)
                top_data = self.get_info.get_tabel_info()
                left_items, excel_name = self.get_info.get_file_and_excel_info()
            else:
                # 仅 BD 模式启动，无 HTML 文件夹
                self.get_info = None
                top_data = None
                left_items = []
                excel_name = {}
        self.file_path = file_path  # 存储文件夹路径（解压后目录），供图片模式查找txt文件
        self.sheet_name = sheet_name  # 存储sheet名，供后台线程使用
        self.excel_path = excel_path  # 存储Excel路径，供BD模式导出使用
        self.json_path = json_path  # 存储JSON路径
        self.bd_file_path = bd_file_path or ""  # 北单HTML文件夹路径（解压后目录）
        self.bd_excel_path = bd_excel_path or ""  # BD专属Excel路径
        self.bd_sheet_name = bd_sheet_name or ""  # BD专属Sheet名称
        self.bd_json_path = bd_json_path or ""  # BD专属JSON路径
        self.html_source_path = html_source_path or file_path or ""  # 原始路径（可能zip）
        self.bd_source_path = bd_source_path or bd_file_path or ""  # 原始BD路径
        # 图片模式 txt 保存目录（软件根目录/txt，按日期分目录）
        self.txt_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'txt'
        )
        self.mapping = {}  # 先初始化空字典，HTML模式下才实际填充

        # 从 QSettings 加载持久化的 MATCH_DICT（有则用，无则默认）
        reload_match_dict()

        # 初始化数据
        if left_items is None:
            self.left_items = ['八神竞猜', '财神密码', '红龙'] + [f"项目{i}" for i in range(4, 15)]
            self.flag = False
        else:
            self.left_items = left_items
            self.flag = True

        if top_data is None:
            self.top_data = [
                ['001', 'xxx', 'a1', 'b1', 'c1','d1'],
                ['002', 'yyy', 'a2', 'b2', 'c2','d2'],
                ['003', 'zzz', 'a3', 'b3', 'c3',"d2"]
            ]
            self.flag = False
        else:
            self.top_data = top_data
            self.flag = True

        # 初始化固定值映射
        self.fixed_values = {row[0]: row[1] for row in self.top_data}
        
        # 初始化Excel相关对象
        if self.flag:
            self.writer = ExcelWriter(excel_path, sheet_name)
            self.excel_first_columns = excel_name  # 实际上是 excel_first_columns 字典
            self.mapping = self.get_info.get_mapping()
            self.header_bases = self.get_info.get_header_bases()
            self.url = self.get_info.get_file_dict()

        # 初始化数据存储，并允许通过update引入新数据
        self.data_storage = {item: {row[0]: list(row[2:]) for row in self.top_data} 
                           for item in self.left_items}
        
        # 从JSON文件加载数据（用于二次整理时引入新数据）
        self._bd_json_restore = None
        if json_path:
            self.data_storage, bd_restore = load_json_to_storage(
                json_path, self.get_info, self.data_storage, logger
            )
            if bd_restore:
                self._bd_json_restore = bd_restore

        # 加载 BD 专属 JSON（如果存在）
        if self.bd_json_path:
            bd_data = load_bd_json(self.bd_json_path, logger)
            if bd_data:
                self._bd_json_restore = bd_data

        self.current_window = None
        self.is_dirty = False          # 未保存修改标记
        self.worker_thread = None      # 后台工作线程引用

        # 确定各模式可用性（哪个文件夹为空，对应模式不可选）
        self._has_html_folder = bool(self.file_path)
        self._has_bd_folder = bool(self.bd_file_path)

        # 默认模式选择
        if not self._has_html_folder and self._has_bd_folder:
            self.data_mode = 'bd'       # 仅有 BD → BD 模式
        else:
            self.data_mode = 'html'     # 有 HTML 或两者都有 → HTML 模式

        # 加载图片模式配置
        pic_categories, pic_mapping, updated_storage = load_pic_config(
            self.data_storage, self.flag, self.top_data
        )
        self.pic_categories = pic_categories
        self.pic_mapping = pic_mapping
        self.data_storage = updated_storage

        self.bd_categories = []        # BD 模式数据（延迟加载）
        self.bd_data_storage = {}
        self._bd_export_rows = {}       # {code: start_row} 记录 BD导出起始行，防止重复写入

        if self.data_mode == 'bd':
            self._load_bd_config_with_progress()  # BD-only 启动时预加载 BD 数据

        self._last_ai_source = ""  # 最近一次 AI 分析的源文件（供历史对话框定位）
        self.init_ui()

        # 如果是 BD 模式，init_ui 中 left_items 为空构建了空列表，需要重建
        if self.data_mode == 'bd':
            self._rebuild_radio_buttons()
            self.refresh_table()

        # Excel 占用状态检测定时器（每 2 秒检测一次）
        self._excel_available = None  # None=未检测，True=可写，False=被占用
        self._excel_check_timer = QTimer(self)
        self._excel_check_timer.timeout.connect(self._check_excel_status)
        self._excel_check_timer.start(2000)
        self._check_excel_status()  # 启动时立即检测一次
        
    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        
        # 左侧面板容器
        left_panel = QVBoxLayout()

        # HTML / 图片 模式切换按钮
        mode_layout = QHBoxLayout()
        active_style = """
            QPushButton { background-color: #2196F3; color: white; font-weight: bold;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #1976D2; }
        """
        inactive_style = """
            QPushButton { background-color: #ccc; color: #666; font-weight: bold;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #bbb; }
        """
        self.html_mode_btn = QPushButton("HTML")
        self.pic_mode_btn = QPushButton("图片")
        self.bd_mode_btn = QPushButton("北单")
        # 初始按钮样式跟随 data_mode
        self.html_mode_btn.setStyleSheet(active_style if self.data_mode == 'html' else inactive_style)
        self.pic_mode_btn.setStyleSheet(active_style if self.data_mode == 'pic' else inactive_style)
        self.bd_mode_btn.setStyleSheet(active_style if self.data_mode == 'bd' else inactive_style)
        self.html_mode_btn.clicked.connect(lambda: self._switch_data_mode('html'))
        self.pic_mode_btn.clicked.connect(lambda: self._switch_data_mode('pic'))
        self.bd_mode_btn.clicked.connect(lambda: self._switch_data_mode('bd'))
        # 根据文件夹情况禁用不可用的模式按钮
        self.html_mode_btn.setEnabled(self._has_html_folder)
        self.bd_mode_btn.setEnabled(self._has_bd_folder)
        mode_layout.addWidget(self.html_mode_btn)
        mode_layout.addWidget(self.pic_mode_btn)
        mode_layout.addWidget(self.bd_mode_btn)
        left_panel.addLayout(mode_layout)

        # 左侧滚动区域
        self.left_scroll = QScrollArea()
        self.left_scroll.setFixedWidth(150)
        self.left_scroll.setWidgetResizable(True)

        self.radio_group = QButtonGroup()
        radio_container = QWidget()
        radio_layout = QVBoxLayout(radio_container)
        radio_layout.setAlignment(Qt.AlignTop)

        # 创建单选按钮（自动分页）
        for idx, item in enumerate(self.left_items):
            radio = QRadioButton(item)
            if item not in self.mapping:
                radio.setStyleSheet("color: red;")
            else:
                radio.setStyleSheet("color: green;")
            self.radio_group.addButton(radio, idx)
            radio_layout.addWidget(radio)
            if idx == 0:
                radio.setChecked(True)

        self.left_scroll.setWidget(radio_container)
        left_panel.addWidget(self.left_scroll)
        main_layout.addLayout(left_panel)
        
        # 右侧表格区域
        right_layout = QVBoxLayout()
        
        self.table = QTableWidget()
        self.table.setItemDelegate(SpaceToZeroDelegate(self.table))
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(['编号', '队伍', '比分1', '比分2', '比分3','比分4'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table)
    

        # 按钮区域 - 三色分行布局
        # ── 绿色按钮行 ──
        green_btn_layout = QHBoxLayout()
        reload_btn = QPushButton("🔄 重新选择路径")
        reload_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #45a049;
            }
            QPushButton:hover { background-color: #45a049; border: 1px solid #3d8b40; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        reload_btn.clicked.connect(self.reload_paths)

        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #45a049;
            }
            QPushButton:hover { background-color: #45a049; border: 1px solid #3d8b40; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        clear_btn.clicked.connect(self._clear_current_page)

        exit_open_btn = QPushButton("📤 退出并打开Excel目录")
        exit_open_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #45a049;
            }
            QPushButton:hover { background-color: #45a049; border: 1px solid #3d8b40; }
            QPushButton:pressed { background-color: #3d8b40; }
        """)
        exit_open_btn.clicked.connect(self._exit_and_open_excel_dir)

        green_btn_layout.addWidget(reload_btn)
        green_btn_layout.addWidget(clear_btn)
        green_btn_layout.addWidget(exit_open_btn)
        green_btn_layout.addStretch()

        # ── 橙色按钮行 ──
        orange_btn_layout = QHBoxLayout()
        orange_style = """
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #F57C00;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #F57C00; border: 1px solid #E65100; }
            QPushButton:pressed { background-color: #E65100; }
        """

        self.fill_btn = QPushButton("📥 填入数据")
        self.fill_btn.setStyleSheet(orange_style)
        self.fill_btn.clicked.connect(self._on_fill_from_txt)
        self.fill_btn.setVisible(False)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet(orange_style)
        refresh_btn.clicked.connect(self.refresh_table)

        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setStyleSheet(orange_style)
        settings_btn.clicked.connect(self._open_settings)

        self.ai_fill_btn = QPushButton("🤖 AI 填入")
        self.ai_fill_btn.setStyleSheet(orange_style)
        self.ai_fill_btn.clicked.connect(self._on_ai_fill)

        orange_btn_layout.addWidget(self.fill_btn)
        orange_btn_layout.addWidget(refresh_btn)
        orange_btn_layout.addWidget(settings_btn)
        orange_btn_layout.addWidget(self.ai_fill_btn)
        orange_btn_layout.addStretch()

        # ── 蓝色按钮行 ──
        blue_btn_layout = QHBoxLayout()
        blue_style = """
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #1976D2;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #1976D2; border: 1px solid #1565C0; }
            QPushButton:pressed { background-color: #1565C0; }
        """

        open_btn = QPushButton("📂 打开")
        save_btn = QPushButton("💾 保存")
        export_btn = QPushButton("📤 导出")
        sort_btn = QPushButton("📊 排序")
        json_btn = QPushButton("📝 写入JSON")

        open_btn.setStyleSheet(blue_style)
        save_btn.setStyleSheet(blue_style)
        export_btn.setStyleSheet(blue_style)
        sort_btn.setStyleSheet(blue_style)
        json_btn.setStyleSheet(blue_style)

        open_btn.clicked.connect(self.on_open_clicked)
        save_btn.clicked.connect(self.save_changes)
        export_btn.clicked.connect(self.export_data)
        sort_btn.clicked.connect(self.sort)
        json_btn.clicked.connect(self.export_json)

        blue_btn_layout.addWidget(open_btn)
        blue_btn_layout.addWidget(save_btn)
        blue_btn_layout.addWidget(export_btn)
        blue_btn_layout.addWidget(sort_btn)
        blue_btn_layout.addWidget(json_btn)
        blue_btn_layout.addStretch()

        # 添加三行到右侧布局
        right_layout.addLayout(green_btn_layout)
        right_layout.addLayout(orange_btn_layout)
        right_layout.addLayout(blue_btn_layout)
        
        main_layout.addLayout(right_layout)
        self.setCentralWidget(main_widget)
        
        # 初始化显示
        self.radio_group.buttonClicked.connect(self.refresh_table)
        self.refresh_table()
        
        ######### 2025-4-16 新增  ########     
         
        # Excel 占用状态指示灯
        status_row = QHBoxLayout()
        self.excel_status_dot = QLabel()
        self.excel_status_dot.setFixedSize(14, 14)
        self.excel_status_dot.setStyleSheet("background-color: #9E9E9E; border-radius: 7px;")
        self.excel_status_label = QLabel("Excel 未检测")
        self.excel_status_label.setStyleSheet("color: #666; font-size: 10px;")
        status_row.addWidget(self.excel_status_dot)
        status_row.addWidget(self.excel_status_label)
        status_row.addStretch()
        right_layout.addLayout(status_row)

        # 在右侧布局中添加日志输出区域
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)  # 只读模式
        self.log_output.setMaximumHeight(100)  # 限制高度
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 5px;
                font-family: Consolas, monospace;
            }
        """)
        right_layout.addWidget(self.log_output)  # 添加到右侧布局

        # 版本号标签（不起眼的右下角）
        version_label = QLabel("v3.3.0")
        version_label.setStyleSheet("color: #999; font-size: 10px; padding: 2px;")
        version_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        right_layout.addWidget(version_label)

        # 设置日志记录器
        self.logger = setup_logger(self.log_output)

        # 重定向 print 到日志框
        sys.stdout = self  # 自定义 stdout
        
    def write(self, text):
        """捕获 print 输出并重定向到日志"""
        if text.strip():  # 只记录非空文本
            self.logger.info(text.strip())

    def _check_excel_status(self):
        """检测当前 Excel 文件是否可写（Windows 文件锁检测）"""
        excel_path = self.bd_excel_path or self.excel_path
        if not excel_path or not os.path.exists(excel_path):
            self._set_excel_status(None)  # 灰色，文件不存在
            return
        try:
            import msvcrt
            with open(excel_path, 'r+b') as f:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            self._set_excel_status(True)  # 可写 → 绿
        except (PermissionError, OSError):
            self._set_excel_status(False)  # 被占用 → 红

    def _set_excel_status(self, available):
        """更新指示灯状态"""
        if available is True and self._excel_available is not True:
            self._excel_available = True
            self.excel_status_dot.setStyleSheet("background-color: #4CAF50; border-radius: 7px;")
            self.excel_status_label.setText("Excel 可编辑")
        elif available is False and self._excel_available is not False:
            self._excel_available = False
            self.excel_status_dot.setStyleSheet("background-color: #F44336; border-radius: 7px;")
            self.excel_status_label.setText("Excel 被占用")
        elif available is None and self._excel_available is not None:
            self._excel_available = None
            self.excel_status_dot.setStyleSheet("background-color: #9E9E9E; border-radius: 7px;")
            self.excel_status_label.setText("Excel 未检测")

    def _load_pic_config(self):
        """加载图片模式配置（与 mapping_data.txt 同格式：excel值：类别名）"""
        self.pic_categories, self.pic_mapping, self.data_storage = load_pic_config(
            self.data_storage, self.flag, self.top_data
        )

    def _load_bd_config(self):
        """加载北单模式配置 — 从当前选择的 Excel 和 HTML 目录扫描"""
        excel_path = self.bd_excel_path or (self.excel_path if hasattr(self, 'excel_path') and self.excel_path else "")
        html_dir = self.bd_file_path or self.file_path or ""
        sheet_name = self.bd_sheet_name or (self.sheet_name if hasattr(self, 'sheet_name') and self.sheet_name else "")
        self.bd_categories, self.bd_data_storage = load_bd_config(
            excel_path, html_dir, sheet_name, self._bd_json_restore, logger
        )

    def _load_bd_config_with_progress(self):
        """带进度提示的 BD 配置加载"""
        progress = QProgressDialog("正在加载北单模式...", None, 0, 0, self)
        progress.setWindowTitle("加载中")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()
        try:
            self._load_bd_config()
        finally:
            progress.close()

    def _rebuild_radio_buttons(self):
        """根据当前 data_mode 重建左侧单选按钮列表"""
        # 清空按钮组
        for btn in self.radio_group.buttons():
            self.radio_group.removeButton(btn)
        # 清空布局
        container = self.left_scroll.widget()
        if container:
            layout = container.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # 选择对应的列表
        if self.data_mode == 'bd':
            items = self.bd_categories
            mapping = {}
        elif self.data_mode == 'pic':
            items = self.pic_categories
            mapping = self.pic_mapping
        else:
            items = self.left_items
            mapping = self.mapping

        for idx, item in enumerate(items):
            radio = QRadioButton(item)
            if item in mapping:
                radio.setStyleSheet("color: green;")
            else:
                radio.setStyleSheet("color: black;" if self.data_mode == 'bd' else "color: red;")
            self.radio_group.addButton(radio, idx)
            container.layout().addWidget(radio)
            if idx == 0:
                radio.setChecked(True)

    def _switch_data_mode(self, mode):
        """切换数据来源模式"""
        if self.data_mode == mode:
            return
        if mode == 'html' and not self._has_html_folder:
            QMessageBox.warning(self, "警告", "未设置 HTML 文件夹路径，无法切换到 HTML 模式")
            return
        if mode == 'pic' and not self.pic_categories:
            QMessageBox.warning(self, "警告", "未加载图片模式配置，无法切换")
            return

        if mode == 'bd' and not self._has_bd_folder:
            QMessageBox.warning(self, "警告", "未设置北单文件夹路径，无法切换到北单模式")
            return

        self.data_mode = mode

        if mode == 'bd':
            self._load_bd_config_with_progress()
        elif mode == 'html':
            self._rebuild_radio_buttons()

        # 更新按钮样式
        active = """
            QPushButton { background-color: #2196F3; color: white; font-weight: bold;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #1976D2; }
        """
        inactive = """
            QPushButton { background-color: #ccc; color: #666; font-weight: bold;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #bbb; }
        """
        self.html_mode_btn.setStyleSheet(active if mode == 'html' else inactive)
        self.pic_mode_btn.setStyleSheet(active if mode == 'pic' else inactive)
        self.bd_mode_btn.setStyleSheet(active if mode == 'bd' else inactive)
        # 重建单选按钮
        self._rebuild_radio_buttons()
        # "填入数据" 仅对图片模式开放（BD 后续加入AI功能后再启用）
        self.fill_btn.setVisible(mode == 'pic')
        # 刷新表格
        self.refresh_table()

    def _get_today_txt_path(self, category_name):
        """返回当天 txt 文件的完整路径（软件目录/txt/YYYY-MM-DD/类别.txt）"""
        today = datetime.now().strftime('%Y-%m-%d')
        day_dir = os.path.join(self.txt_dir, today)
        os.makedirs(day_dir, exist_ok=True)
        return os.path.join(day_dir, f"{category_name}.txt")

    def _on_fill_from_txt(self):
        """填入数据：图片模式从txt，BD模式从HTML详情文件解析比分"""
        selected_item = self.radio_group.checkedButton().text()

        if self.data_mode == 'bd':
            self._fill_bd_from_html(selected_item)
            return

        # 图片模式：从当天日期目录读取 txt
        txt_path = self._get_today_txt_path(selected_item)
        if not os.path.exists(txt_path):
            QMessageBox.warning(self, "警告", f"未找到文件: {txt_path}")
            return

        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            txt_data = {}
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 1:
                    code = parts[0]
                    values = [apply_keyboard_mappings(v) for v in parts[1:5]]
                    while len(values) < 4:
                        values.append('')
                    txt_data[code] = values

            filled = 0
            for row in range(self.table.rowCount()):
                code_item = self.table.item(row, 0)
                if code_item is None:
                    continue
                code = code_item.text()
                if code in txt_data:
                    for col_idx, val in enumerate(txt_data[code], start=2):
                        if col_idx < self.table.columnCount():
                            self.table.setItem(row, col_idx, QTableWidgetItem(val))
                    filled += 1

            if filled > 0:
                self.is_dirty = True
                self.logger.info(f"已从 {txt_path} 填入 {filled}/{len(txt_data)} 条数据")
                self.log_output.append(f"已从 {os.path.basename(txt_path)} 填入 {filled} 条数据")
            else:
                QMessageBox.warning(self, "提示", "未找到匹配的编号")
        except Exception as e:
            QMessageBox.warning(self, "警告", f"读取失败: {str(e)}")

    def _on_ai_fill(self):
        """AI 填入：选择新预测或查看历史"""
        msg = QMessageBox(self)
        msg.setWindowTitle("AI 填入")
        msg.setText("请选择操作：")
        btn_new = msg.addButton("🤖 新预测", QMessageBox.ActionRole)
        btn_history = msg.addButton("📂 历史预测", QMessageBox.ActionRole)
        msg.addButton("取消", QMessageBox.RejectRole)
        msg.exec_()
        clicked = msg.clickedButton()

        if clicked == btn_new:
            start_dir = self.file_path or self.bd_file_path or ""
            file, _ = QFileDialog.getOpenFileName(
                self, "选择HTML或图片文件",
                directory=start_dir,
                filter="HTML Files (*.html);;图片文件 (*.png *.jpg *.jpeg *.bmp)"
            )
            if file:
                self._ai_fill_from_path(file)
        elif clicked == btn_history:
            self._show_ai_history()

    def _show_ai_history(self):
        """查看历史 AI 预测结果（带日期/文件名筛选）"""
        current_file = os.path.splitext(os.path.basename(self._last_ai_source or ""))[0]
        dlg = AiHistoryDialog(current_file=current_file, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        filepath = dlg.get_selected_filepath()
        if not filepath:
            return

        data = ai_storage.load_ai_result(filepath)
        predictions = data.get("predictions", [])
        if not predictions:
            QMessageBox.information(self, "提示", "该记录无预测数据")
            return

        mode_hint = 'bd' if data.get('mode') == 'bd' else 'jc'
        dialog = AiPreviewDialog(
            predictions, mode_hint, parent=self,
            raw=data.get("raw", ""),
            method=data.get("method", ""),
            source_file=data.get("source_file", ""),
        )
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected()
            if not selected:
                return
            self._apply_ai_predictions(selected, source_file=data.get("source_file", ""))
            self.logger.info(f"从历史复用 {len(selected)} 条预测")
            self.log_output.append(f"✅ 从历史复用 {len(selected)} 条预测")

    def _ai_fill_from_html(self, html_path: str):
        """HTML 查看器调用：分析指定 HTML 文件"""
        self._ai_fill_from_path(html_path)

    def _ai_fill_from_path(self, path: str):
        """AI 分析指定 HTML/图片文件 → 预览 → 填入（查看器和主窗口共用）"""
        self._last_ai_source = path  # 记录当前源文件，供历史对话框定位
        # 检查 API Key
        if not ai_config.get_api_key():
            QMessageBox.warning(
                self, "提示",
                "未配置 AI API Key\n请在 config.ini 的 [ai] 段设置 ai/api_key，或稍后在设置中配置"
            )
            return

        # 按扩展名分流 HTML / 图片
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.png', '.jpg', '.jpeg', '.bmp'):
            analyzer = ai_handler.extract_predictions_from_image
            progress_msg = "AI 正在识别图片...（首次加载 OCR 模型较慢）"
            analyzer_kwargs = {}
        else:
            analyzer = ai_handler.extract_predictions_from_html
            progress_msg = "AI 正在分析 HTML 文件..."
            # 传当前模式的 Excel 白名单约束编号
            if self.data_mode == 'bd':
                analyzer_kwargs = {
                    'excel_path': self.bd_excel_path or "",
                    'sheet_name': self.bd_sheet_name or "",
                    'mode': 'bd',
                }
            else:
                analyzer_kwargs = {
                    'excel_path': self.excel_path or "",
                    'sheet_name': self.sheet_name or "",
                    'mode': 'jc',
                }

        # 调 AI（带进度提示）
        progress = QProgressDialog(progress_msg, None, 0, 0, self)
        progress.setWindowTitle("AI 分析中")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()
        try:
            result = analyzer(path, **analyzer_kwargs)
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "错误", f"AI 调用失败：{str(e)}")
            return
        progress.close()

        # 自动保存 AI 结果（防误关窗口后结果丢失，可复用）
        mode_hint = 'bd' if self.data_mode == 'bd' else 'jc'
        try:
            ai_storage.save_ai_result(result, source_file=path, mode=mode_hint)
        except Exception:
            pass

        predictions = result.get("predictions", [])
        if not predictions:
            QMessageBox.information(self, "提示", "AI 未提取到预测结果（今天可能无数据）")
            return

        # 预览确认
        dialog = AiPreviewDialog(
            predictions, self.data_mode, parent=self,
            raw=result.get("raw", ""),
            method=result.get("method", ""),
            source_file=path,
        )
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected()
            if not selected:
                QMessageBox.information(self, "提示", "未勾选任何结果")
                return
            self._apply_ai_predictions(selected, source_file=path)
            self.logger.info(f"AI 填入 {len(selected)} 条预测")
            self.log_output.append(f"✅ AI 已填入 {len(selected)} 条预测")

    def _apply_ai_predictions(self, predictions: list, source_file: str = ""):
        """将确认的 AI 预测写入对应模式的数据存储"""
        if self.data_mode == 'bd':
            self._apply_ai_bd(predictions)
        else:
            self._apply_ai_jc(predictions, source_file=source_file)
        self.is_dirty = True
        self.refresh_table()

    def _apply_ai_bd(self, predictions: list):
        """BD 模式：写入 bd_data_storage"""
        for pred in predictions:
            code = str(pred.get("code", ""))
            scores = pred.get("scores", [])
            # 规范化 scores：统一转字符串，过滤非 2 位数字
            normalized = []
            for s in scores:
                if isinstance(s, list):
                    pair = [str(x).strip() for x in s[:2]]
                else:
                    pair = [str(s).strip()]
                pair = [x for x in pair if x.isdigit() and len(x) == 2]
                if pair:
                    normalized.append(pair)
            # 按 code 匹配 bd_data_storage
            for info in self.bd_data_storage.values():
                if info.get("code") == code:
                    info["scores"] = normalized
                    break

    def _apply_ai_jc(self, predictions: list, source_file: str = ""):
        """JC/HTML 模式：写入 data_storage"""
        # 机构名：pred 无 label 时，从 source_file 文件名推断
        default_category = os.path.splitext(os.path.basename(source_file or ""))[0] if source_file else ""
        for pred in predictions:
            category = pred.get("label", "") or pred.get("category", "") or default_category
            code = str(pred.get("code", "")).zfill(3)
            scores = pred.get("scores", [])
            # 扁平化 scores 到 4 个比分位
            flat = []
            for s in scores:
                if isinstance(s, list):
                    flat.extend(str(x).strip() for x in s)
                else:
                    flat.append(str(s).strip())
            vals = [x for x in flat if x]
            while len(vals) < 4:
                vals.append("")
            vals = vals[:4]
            # 写入匹配的 category+code
            if category in self.data_storage and code in self.data_storage[category]:
                self.data_storage[category][code] = vals

    def _fill_bd_from_html(self, selected_item):
        """BD 模式：从北单N.html 详情文件中解析比分并填入"""
        bd_info = self.bd_data_storage.get(selected_item, {})
        code = bd_info.get("code", "")
        html_dir = self.bd_file_path or self.file_path
        if not html_dir or not os.path.isdir(html_dir):
            QMessageBox.warning(self, "警告", "未设置北单文件夹路径")
            return

        detail_scores = parse_bd_detail(html_dir)
        if code in detail_scores:
            raw = detail_scores[code]
            # 严格过滤：排除赔率/盘口噪声（如 6-17, 3-15, 12-4）
            # 足球单边比分 ≤ 7，超过此值视为非比分数据
            filtered = []
            for a, b in raw:
                try:
                    ia, ib = int(a), int(b)
                    if ia <= 7 and ib <= 7:
                        filtered.append([a, b])
                except ValueError:
                    continue
            bd_info["scores"] = filtered
            self.refresh_table()
            self.logger.info(f"BD 填入数据: {selected_item} → {len(raw)}组原始, {len(filtered)}组有效")
            self.log_output.append(f"已从 北单{code}.html 填入 {len(filtered)} 组比分")
        else:
            QMessageBox.warning(self, "警告", f"未从文件中提取到比分数据")

    def refresh_table(self):
        """刷新表格"""
        try:
            btn = self.radio_group.checkedButton()
            if btn is None:
                self.table.setRowCount(0)
                return
            selected_item = btn.text()

            if self.data_mode == 'bd':
                self._refresh_table_bd(selected_item)
                return

            current_data = self.data_storage[selected_item]

            self.table.setRowCount(len(current_data))
            for row_idx, (code, values) in enumerate(current_data.items()):
                # 编号
                item = QTableWidgetItem(code)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, 0, item)

                # 固定值
                item = QTableWidgetItem(self.fixed_values[code])
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, 1, item)

                # 可编辑字段
                for col_idx, value in enumerate(values, start=2):
                    self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))
        except Exception as e:
            logger.exception("刷新表格时发生错误")
            QMessageBox.warning(self, "警告", f"{e}")

    def _refresh_table_bd(self, selected_item):
        """BD 模式表格刷新 — 行=预测实例，列=比分槽位"""
        bd_info = self.bd_data_storage.get(selected_item, {})
        scores = bd_info.get("scores", [])
        home = bd_info.get("home", "")
        away = bd_info.get("away", "")

        # 至少显示 30 行，不足则补空行
        min_rows = 30
        display_scores = list(scores) if scores else []
        if len(display_scores) < min_rows:
            display_scores += [["", "", "", ""] for _ in range(min_rows - len(display_scores))]
        self.table.setRowCount(len(display_scores))

        for row_idx, score_set in enumerate(display_scores):
            item = QTableWidgetItem(str(row_idx + 1))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 0, item)

            team_str = f"{home} VS {away}" if home else selected_item
            item = QTableWidgetItem(team_str)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 1, item)

            for col_idx, val in enumerate(score_set[:4], start=2):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(val))
                
    def save_changes(self):
        """
        保存修改
        """
        try:
            selected_item = self.radio_group.checkedButton().text()
            for row in range(self.table.rowCount()):
                code = self.table.item(row, 0).text()
                new_values = [apply_keyboard_mappings(self.table.item(row, col).text()) for col in range(2, 6)]
                if self.data_mode == 'bd':
                    # BD: 全量重建 scores，清掉旧数据避免 HTML 噪声残留
                    if selected_item not in self.bd_data_storage:
                        bd_info = self.bd_data_storage.get(selected_item, {})
                        self.bd_data_storage[selected_item] = {
                            "code": bd_info.get("code", ""),
                            "home": bd_info.get("home", ""),
                            "away": bd_info.get("away", ""),
                            "scores": [],
                        }
                    new_scores = []
                    for r in range(self.table.rowCount()):
                        vals = [apply_keyboard_mappings(self.table.item(r, c).text())
                                for c in range(2, 6)]
                        if any(v.strip() for v in vals):
                            new_scores.append(vals)
                    self.bd_data_storage[selected_item]["scores"] = new_scores
                    break  # BD 模式一次性重建，不逐行循环
                else:
                    self.data_storage[selected_item][code] = new_values
            self.is_dirty = True
        except Exception as e:
            logger.exception("保存数据时发生错误")
            QMessageBox.warning(self, "警告", f"保存失败：{str(e)}")

    def _clear_current_page(self):
        """清空当前页面所有输入内容及已保存数据"""
        reply = QMessageBox.question(
            self, '确认清空',
            '将清空当前页面所有输入内容及已保存数据，是否继续？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            selected_item = self.radio_group.checkedButton().text()
            # 清空表格显示
            for row in range(self.table.rowCount()):
                for col in range(2, self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item is not None:
                        item.setText("")
            # 清空 data_storage 中对应的数据
            if self.data_mode == 'bd':
                if selected_item in self.bd_data_storage:
                    self.bd_data_storage[selected_item]["scores"] = []
            elif selected_item in self.data_storage:
                for code in self.data_storage[selected_item]:
                    self.data_storage[selected_item][code] = ['', '', '', '']
                self.is_dirty = True
            self.logger.info(f"已清空 *{selected_item}* 的输入内容")
        except Exception as e:
            logger.exception("清空页面时发生错误")
            QMessageBox.warning(self, "警告", f"清空失败：{str(e)}")

    def _on_child_window_destroyed(self, obj):
        """子窗口销毁时，清除引用（destroyed 信号在 WA_DeleteOnClose 后可能传递 None）"""
        if obj is None or self.current_window is obj:
            self.current_window = None

    def on_open_clicked(self):
        """
        打开文件：HTML模式打开HTML，图片模式打开txt
        """
        if self.current_window:
            try:
                self.current_window.close()
            except RuntimeError:
                pass  # C++ 对象已被 WA_DeleteOnClose 销毁
            self.current_window = None
        selected_item = self.radio_group.checkedButton().text()

        if self.data_mode == 'pic':
            self._show_pic_txt_dialog(selected_item)
        elif self.data_mode == 'bd':
            # BD 模式：从北单专用目录查找北单N.html
            bd_info = self.bd_data_storage.get(selected_item, {})
            code = bd_info.get("code", "")
            bd_dir = self.bd_file_path or self.file_path
            found = None
            if bd_dir and os.path.isdir(bd_dir):
                code_int = int(code)
                for fpath in glob.glob(os.path.join(bd_dir, '**', '*.html'), recursive=True):
                    fname = os.path.basename(fpath)
                    if fname == 'A数量.html':
                        continue
                    m = re.search(r'北单(\d+)', fname)
                    if m and int(m.group(1)) == code_int:
                        found = fpath
                        break
            if found:
                self.current_window = NewWindow(selected_item, html_base_path=found, parent=self)
                self.current_window.destroyed.connect(self._on_child_window_destroyed)
                self.current_window.show()
            else:
                QMessageBox.warning(self, "警告", f"未找到比赛文件: 北单{code}")
        else:
            # HTML模式：原有逻辑
            try:
                url = self.url[selected_item]
                self.current_window = NewWindow(selected_item,
                                              html_base_path=url,
                                              parent=self)
                self.current_window.destroyed.connect(self._on_child_window_destroyed)
                self.current_window.show()
            except:
                QMessageBox.warning(self, "警告", "文件路径不存在，或者文件名称错误")

    def _show_reload_splash(self):
        """重新选择路径后显示数据读取加载提示"""
        splash = QDialog(None)
        splash.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        splash.setFixedSize(240, 120)
        layout = QVBoxLayout(splash)
        label = QLabel("📊 正在读取数据...")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 15px; font-weight: bold; color: #333;")
        layout.addWidget(label)
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            splash.move(geo.center() - splash.rect().center())
        splash.show()
        QApplication.processEvents()
        return splash

    def _show_pic_txt_dialog(self, selected_item):
        """Pic模式：可编辑的txt对话框，文件不存在时保存即创建"""
        # 保存到软件目录/txt/当天日期/类别.txt
        txt_path = self._get_today_txt_path(selected_item)

        # 读取已有内容（不存在则为空）
        content = ""
        if os.path.exists(txt_path):
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception:
                QMessageBox.warning(self, "警告", "读取txt文件失败")
                return

        dialog = QDialog(self)
        dialog.setAttribute(Qt.WA_DeleteOnClose)
        dialog.setWindowTitle(f"图片数据 - {selected_item}")
        dialog.setGeometry(200, 200, 600, 400)
        layout = QVBoxLayout()

        text_edit = QTextEdit()
        text_edit.setPlainText(content)
        layout.addWidget(text_edit)

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")

        def on_save():
            try:
                os.makedirs(os.path.dirname(txt_path), exist_ok=True)
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(text_edit.toPlainText())
                self.logger.info(f"已保存: {txt_path}")
            except Exception as e:
                QMessageBox.warning(dialog, "错误", f"保存失败: {str(e)}")
                return
            dialog.accept()

        save_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        dialog.setLayout(layout)
        self.current_window = dialog
        self.current_window.destroyed.connect(self._on_child_window_destroyed)
        self.current_window.show()

    def export_data(self):
        """
        导出数据 - 主线程收集验证，后台线程写入（不阻塞UI）
        """
        # Excel 被占用时拦截导出
        if self._excel_available is False:
            QMessageBox.warning(self, "警告", "Excel 文件被占用，请先关闭外部打开的 Excel 再导出")
            return
        self.save_changes()
        selected_item = self.radio_group.checkedButton().text()

        # BD 模式：专用导出路径
        if self.data_mode == 'bd':
            self._export_bd(selected_item)
            return

        is_pic = (self.data_mode == 'pic' and selected_item in self.pic_categories)

        try:
            ex_header = self.pic_mapping[selected_item] if is_pic else self.mapping[selected_item]
        except Exception as e:
            logger.exception(f"映射表错误: 未找到键 '{selected_item}'")
            QMessageBox.warning(self, "错误", f"'{selected_item}'未匹配成功，请检查映射表")
            return 0

        logger.info(f'开始收集写入操作 *{selected_item}*')

        # 第一阶段：收集写操作并逐项验证（主线程，可弹窗）
        write_ops, invalid_items = collect_export_write_ops(
            self.get_info, self.data_storage, selected_item,
            ex_header, is_pic, self.excel_first_columns, logger
        )

        # 发现无效数据时弹窗确认
        if invalid_items:
            detail = "\n".join(invalid_items[:20])
            if len(invalid_items) > 20:
                detail += f"\n... 还有 {len(invalid_items) - 20} 条"
            message = f"以下数据验证未通过:\n{detail}\n\n是否跳过无效项并继续写入？"
            reply = QMessageBox.question(self, '验证失败', message,
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                logger.warning(f'*{selected_item}* 用户取消写入（验证未通过）')
                return 0

        if not write_ops:
            logger.warning(f'*{selected_item}* 无有效写入操作')
            return 0

        logger.info(f'*{selected_item}* 共 {len(write_ops)} 条写入操作，开始后台写入')

        # 第二阶段：后台线程写入
        self._run_write_worker(write_ops, f"导出 {selected_item}")

    def _export_bd(self, selected_item):
        """BD 模式导出 — 纵向追加写入，无需映射/MATCH_DICT"""
        # Excel 被占用时拦截导出
        if self._excel_available is False:
            QMessageBox.warning(self, "警告", "Excel 文件被占用，请先关闭外部打开的 Excel 再导出")
            return
        bd_info = self.bd_data_storage.get(selected_item, {})
        scores = bd_info.get("scores", [])
        code = bd_info.get("code", "")
        if not scores or not code:
            QMessageBox.warning(self, "警告", "无数据可导出")
            return

        # 验证每个比分是否为 2 位数
        invalid_items = []
        for i, score_set in enumerate(scores):
            for col_idx, s in enumerate(score_set[:4]):
                s = str(s).strip()
                if s and not re.fullmatch(r'\d{2}', s):
                    invalid_items.append(f"第{i+1}行第{col_idx+1}列: \"{s}\"")

        if invalid_items:
            detail = "\n".join(invalid_items[:20])
            if len(invalid_items) > 20:
                detail += f"\n... 还有 {len(invalid_items) - 20} 条"
            reply = QMessageBox.question(
                self, '验证失败',
                f"以下数据不是有效的 2 位比分，是否跳过并继续写入？\n\n{detail}",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        excel_path = self.bd_excel_path or (self.excel_path if hasattr(self, 'excel_path') and self.excel_path else "")
        if not excel_path:
            QMessageBox.warning(self, "警告", "未设置 BD Excel 路径，请先配置")
            return
        sheet = self.bd_sheet_name or (self.sheet_name if hasattr(self, 'sheet_name') else None)

        success, message = export_bd_data(bd_info, excel_path, sheet, self._bd_export_rows, logger)
        if success:
            self.is_dirty = False
            self.logger.info(f"BD 导出完成: {selected_item} → {len(scores)} 行")
        else:
            QMessageBox.warning(self, "错误", message)

    def _run_write_worker(self, write_ops, task_name):
        """启动后台写入线程，不阻塞UI"""
        # 等待上一个线程完全结束
        if self.worker_thread is not None:
            if self.worker_thread.isRunning():
                QMessageBox.warning(self, "提示", "已有写入任务正在进行，请等待完成")
                return
            # 等待线程彻底退出
            self.worker_thread.wait(3000)
            self.worker_thread = None

        from src.worker import ExcelWriteWorker

        self.worker_thread = QThread()
        self.worker = ExcelWriteWorker(
            self.writer.excel_path,
            getattr(self, 'sheet_name', None),
            write_ops
        )
        self.worker.moveToThread(self.worker_thread)

        # 连接信号
        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self._on_write_finished)
        self.worker.progress.connect(self._on_write_progress)
        self.worker_thread.finished.connect(self._on_thread_finished)

        self.worker_thread.start()

        # 进度对话框
        self.progress_dialog = QProgressDialog(
            f"正在{task_name}...", None, 0, len(write_ops), self
        )
        self.progress_dialog.setWindowTitle("请稍候")
        self.progress_dialog.setCancelButton(None)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

    def _on_thread_finished(self):
        """线程完成清理（避免 lambda 引用被覆盖的问题）"""
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        self.worker_thread = None

    def _on_write_progress(self, current, total):
        """写入进度更新（主线程）"""
        if hasattr(self, 'progress_dialog') and self.progress_dialog:
            self.progress_dialog.setValue(current)
            self.progress_dialog.setLabelText(f"正在写入... ({current}/{total})")

    def _on_write_finished(self, success, message):
        """写入完成回调（主线程）"""
        try:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None

            if success:
                self.is_dirty = False
                logger.info(message)
                if hasattr(self, 'log_output') and self.log_output:
                    self.log_output.append(f"✅ {message}")
            else:
                logger.error(message)
                QMessageBox.critical(self, "错误", message)
        except RuntimeError:
            pass  # 窗口已销毁，忽略回调
    
    def sort(self):
        """排序 - 内存统计在主线程，写入在后台线程。BD 模式使用专用排序路径。"""
        try:
            self.save_changes()

            if self.data_mode == 'bd':
                self._sort_bd()
                return

            dict_counter = collect_sort_stats(self.data_storage, self.pic_categories, logger)

            write_ops = []
            for column, contents in dict_counter.items():
                try:
                    _, column_location = self.get_info.get_location(header_num=column)
                    write_ops.append((84, column_location, contents))
                except Exception as e:
                    logger.exception(f"排序写入失败 - 列: {column}")

            if write_ops:
                self._run_write_worker(write_ops, "排序")

            logger.info("排序完成")
            return dict_counter
        except Exception as e:
            logger.exception("排序过程中发生错误")
            QMessageBox.critical(self, "错误", f"排序失败：{str(e)}")
            return None

    def _sort_bd(self):
        """BD 排序 — 统计 bd_data_storage 中比分频率，纵向写入 Excel row 84"""
        try:
            excel_path = self.bd_excel_path or (self.excel_path if hasattr(self, 'excel_path') and self.excel_path else "")
            if not excel_path:
                QMessageBox.warning(self, "警告", "未设置 BD Excel 路径，请先配置")
                return
            sheet = self.bd_sheet_name or (self.sheet_name if hasattr(self, 'sheet_name') else None)
            sort_bd_data(self.bd_data_storage, excel_path, sheet, logger)
            self.is_dirty = False
        except Exception as e:
            logger.exception("BD 排序失败")
            QMessageBox.critical(self, "错误", f"BD 排序失败：{str(e)}")

    def export_json(self):
        """导出JSON文件 - BD模式单独保存"""
        try:
            if not os.path.exists("./json"):
                os.makedirs("./json")

            if self.data_mode == 'bd':
                json_path = f"./json/bd_{datetime.now().strftime('%Y-%m-%d')}.json"
                # BD 格式：{code: {home, away, scores: [[...]]}}
                export_data = {}
                for label, info in self.bd_data_storage.items():
                    if info.get("scores"):
                        export_data[label] = {
                            "code": info["code"],
                            "home": info["home"],
                            "away": info["away"],
                            "scores": info["scores"],
                        }
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, ensure_ascii=False, indent=4)
                logger.info(f"BD JSON 导出成功: {json_path} ({len(export_data)} 场比赛)")
                self.is_dirty = False
                return True

            # JC/HTML 模式（原有逻辑）
            # 转置为 code→category→scores 格式
            new_json_data = {}
            for category, codes in self.data_storage.items():
                for code, scores in codes.items():
                    if code not in new_json_data:
                        new_json_data[code] = {}
                    new_json_data[code][category] = scores

            json_path = f"./json/{datetime.now().strftime('%Y-%m-%d')}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(new_json_data, f, ensure_ascii=False, indent=4)
            logger.info(f"JSON文件导出成功: {json_path}")
            self.is_dirty = False
            return True
        except Exception as e:
            logger.exception("JSON导出失败")
            QMessageBox.critical(self, "错误", f"JSON导出失败：{str(e)}")
            return False

    def closeEvent(self, event):
        """关闭主窗口时保存窗口位置和大小"""
        if hasattr(self, '_excel_check_timer'):
            self._excel_check_timer.stop()  # 停止 Excel 检测定时器
        geom = self.saveGeometry()
        settings = QSettings("config.ini", QSettings.IniFormat)
        settings.setValue("window/geometry", geom)
        super().closeEvent(event)

    def _open_excel_dir(self):
        """在资源管理器中打开当前 Excel 所在目录"""
        excel_path = self.excel_path or self.bd_excel_path
        if not excel_path or not os.path.exists(excel_path):
            QMessageBox.warning(self, "提示", "Excel 文件路径无效，无法打开目录")
            return
        dir_path = os.path.dirname(excel_path)
        try:
            os.startfile(dir_path)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开目录失败: {str(e)}")

    def _exit_and_open_excel_dir(self):
        """退出并打开 Excel 所在目录（三选一确认）"""
        reply = QMessageBox(self)
        reply.setWindowTitle("退出选项")
        reply.setText("请选择退出方式：")
        btn_save_open = reply.addButton("💾 保存，退出并打开文件夹", QMessageBox.ActionRole)
        btn_save_exit = reply.addButton("💾 保存并退出", QMessageBox.ActionRole)
        btn_no_save = reply.addButton("🚪 退出不保存", QMessageBox.ActionRole)
        reply.addButton("取消", QMessageBox.RejectRole)
        reply.exec_()
        clicked = reply.clickedButton()

        if clicked == btn_save_open:
            if self.export_json():
                self._open_excel_dir()   # 先打开目录
                self.close()             # 再关闭
        elif clicked == btn_save_exit:
            if self.export_json():
                self.close()
        elif clicked == btn_no_save:
            confirm = QMessageBox.question(
                self, "确认退出",
                "该选项不保存已有内容，确定退出？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.close()

    def reload_paths(self):
        """
        重新选择路径并重新加载数据
        """
        try:
            # 先关闭打开的HTML窗口
            if self.current_window:
                try:
                    self.current_window.close()
                except RuntimeError:
                    pass
                self.current_window = None

            # 确认对话框
            dirty_msg = "，且有未保存的修改" if self.is_dirty else ""
            reply = QMessageBox.question(
                self, '确认重新选择',
                f'重新选择路径将关闭当前窗口{dirty_msg}，未保存的数据将会丢失。\n是否继续？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            # 关闭当前窗口前清理日志处理器（防止旧 QTextEdit 引用残留）
            for h in list(logger.handlers):
                if isinstance(h, QTextEditLogger):
                    logger.removeHandler(h)
            self.close()

            # 重新运行路径选择器
            from window.table_qt_2 import PathSelector
            path_selector = PathSelector()
            result = path_selector.exec_()
            
            if result == QDialog.Accepted:
                (folder_path, excel_path, json_path, sheet_name,
                 bd_folder, bd_excel, bd_sheet, bd_json) = path_selector.selected_paths

                # 保留原始路径（设置界面显示用）
                folder_path_raw = folder_path
                bd_folder_raw = bd_folder

                # 显示数据读取加载提示
                data_splash = self._show_reload_splash()

                # ZIP 解压
                try:
                    if folder_path:
                        folder_path = ensure_extracted(folder_path, logger)
                    if bd_folder:
                        bd_folder = ensure_extracted(bd_folder, logger)
                except ValueError as e:
                    data_splash.close()
                    QMessageBox.critical(None, "解压错误", str(e))
                    return

                # 验证路径有效性
                if not folder_path and not bd_folder:
                    data_splash.close()
                    QMessageBox.critical(None, "错误", "必须选择 HTML 文件夹或北单文件夹")
                    return
                if folder_path and not excel_path:
                    data_splash.close()
                    QMessageBox.critical(None, "错误", "选择了 HTML 文件夹则必须选择 Excel 文件")
                    return
                if excel_path and not sheet_name:
                    data_splash.close()
                    QMessageBox.critical(None, "错误", "必须选择有效的 Sheet")
                    return

                # 保存路径到 config.ini（供下次"自动填入"使用）
                settings = QSettings("config.ini", QSettings.IniFormat)
                if not settings.value("paths/mapping_path"):
                    settings.setValue("paths/mapping_path", "mapping/mapping_data.txt")
                settings.setValue("paths/html_folder_path", folder_path_raw or "")
                settings.setValue("paths/excel_path", excel_path or "")
                settings.setValue("paths/json_path", json_path or "")
                settings.setValue("paths/sheet_name", sheet_name or "")
                settings.setValue("paths/bd_folder_path", bd_folder_raw or "")
                settings.setValue("paths/bd_excel_path", bd_excel or "")
                settings.setValue("paths/bd_sheet_name", bd_sheet or "")
                settings.setValue("paths/bd_json_path", bd_json or "")

                # 创建新的主窗口实例
                new_window = EnhancedDataEditor(excel_path=excel_path,
                                               file_path=folder_path,
                                               json_path=json_path,
                                               sheet_name=sheet_name,
                                               bd_file_path=bd_folder or "",
                                               bd_excel_path=bd_excel or "",
                                               bd_sheet_name=bd_sheet or "",
                                               bd_json_path=bd_json or "",
                                               html_source_path=folder_path_raw,
                                               bd_source_path=bd_folder_raw)
                new_window.show()
                # 新窗口就绪后关闭加载提示
                data_splash.close()

        except Exception as e:
            logger.exception("重新加载路径时发生错误")
            QMessageBox.critical(None, "错误", f"重新加载失败：{str(e)}")

    def _open_settings(self):
        """打开设置对话框"""
        settings = QSettings("config.ini", QSettings.IniFormat)
        current_paths = {
            'mapping_path': settings.value("paths/mapping_path", "mapping/mapping_data.txt"),
            'html_folder_path': self.html_source_path,
            'excel_path': self.excel_path or "",
            'json_path': self.json_path or "",
            'sheet_name': self.sheet_name or "",
            'bd_folder_path': self.bd_source_path,
            'bd_excel_path': self.bd_excel_path or "",
            'bd_sheet_name': self.bd_sheet_name or "",
            'bd_json_path': self.bd_json_path or "",
        }

        dialog = SettingsDialog(current_paths, parent=self, txt_dir=self.txt_dir)
        if dialog.exec_() == QDialog.Accepted:
            new_paths = dialog.get_paths()
            # 重载 MATCH_DICT 和键盘映射（可能在设置中已修改）
            reload_match_dict()
            self.table.setItemDelegate(SpaceToZeroDelegate(self.table))

            # 仅当路径变化时才重新加载数据（只改 AI/映射配置时不刷新，避免丢失未保存内容）
            if self._paths_changed(new_paths):
                self._reload_with_new_paths(new_paths)
            else:
                self.logger.info("设置已更新（仅 AI/映射配置），数据保持不变")

    def _paths_changed(self, new_paths: dict) -> bool:
        """判断路径是否有变化（决定是否重新加载数据）"""
        cur = {
            'html_folder_path': self.html_source_path,
            'excel_path': self.excel_path or "",
            'json_path': self.json_path or "",
            'sheet_name': self.sheet_name or "",
            'bd_folder_path': self.bd_source_path,
            'bd_excel_path': self.bd_excel_path or "",
            'bd_sheet_name': self.bd_sheet_name or "",
            'bd_json_path': self.bd_json_path or "",
        }
        for key, cur_val in cur.items():
            new_val = new_paths.get(key, "") or ""
            if new_val != cur_val:
                return True
        return False

    def _reload_with_new_paths(self, new_paths: dict):
        """根据新路径重新初始化数据"""
        html_folder = new_paths.get('html_folder_path', self.html_source_path)
        excel_path = new_paths.get('excel_path', self.excel_path or "")
        json_path = new_paths.get('json_path', self.json_path or "")
        mapping_path = new_paths.get(
            'mapping_path',
            QSettings("config.ini", QSettings.IniFormat).value("paths/mapping_path", "mapping/mapping_data.txt")
        )
        sheet_name = new_paths.get('sheet_name', self.sheet_name)

        # BD 路径
        bd_folder = new_paths.get('bd_folder_path', self.bd_source_path)
        bd_excel = new_paths.get('bd_excel_path', self.bd_excel_path or "")
        bd_sheet = new_paths.get('bd_sheet_name', self.bd_sheet_name or "")
        bd_json = new_paths.get('bd_json_path', self.bd_json_path or "")

        if not html_folder or not excel_path:
            QMessageBox.warning(self, "警告", "HTML文件夹路径和Excel路径不能为空")
            return

        if not sheet_name:
            QMessageBox.warning(self, "警告", "请选择Excel Sheet")
            return

        try:
            # 如果是 .zip 路径则自动解压（JC 和 BD）
            html_source = html_folder
            html_folder = ensure_extracted(html_folder, logger)
            bd_source = bd_folder
            bd_folder = ensure_extracted(bd_folder, logger)

            result = reinitialize_data(html_folder, excel_path, sheet_name, mapping_path, logger)

            # 更新 JC 路径
            self.html_source_path = html_source or ""
            self.get_info = result['get_info']
            self.file_path = html_folder
            self.excel_path = excel_path or ""
            self.json_path = json_path or ""
            self.sheet_name = sheet_name
            self.top_data = result['top_data']
            self.left_items = result['left_items']
            self.flag = True
            self.fixed_values = result['fixed_values']
            self.writer = ExcelWriter(excel_path, sheet_name)
            self.excel_first_columns = result['excel_name']
            self.mapping = result['mapping']
            self.header_bases = result['header_bases']
            self.url = result['url']
            self.data_storage = result['data_storage']

            # 更新 BD 路径
            self.bd_source_path = bd_source or ""
            self.bd_file_path = bd_folder or ""
            self.bd_excel_path = bd_excel or ""
            self.bd_sheet_name = bd_sheet or ""
            self.bd_json_path = bd_json or ""
            self._has_bd_folder = bool(self.bd_file_path)
            if hasattr(self, 'bd_mode_btn'):
                self.bd_mode_btn.setEnabled(self._has_bd_folder)

            # 重新加载图片模式配置
            self._load_pic_config()

            # 重新导入 JSON 数据
            if json_path and os.path.exists(json_path):
                self.data_storage, _ = load_json_to_storage(
                    json_path, self.get_info, self.data_storage, logger
                )

            # 重建单选按钮并刷新表格
            self._rebuild_radio_buttons()
            self.refresh_table()

            # 保存路径到 QSettings（用原始路径，非临时目录）
            settings = QSettings("config.ini", QSettings.IniFormat)
            settings.setValue("paths/mapping_path", mapping_path)
            settings.setValue("paths/html_folder_path", html_source)
            settings.setValue("paths/excel_path", excel_path)
            settings.setValue("paths/json_path", json_path)
            settings.setValue("paths/sheet_name", sheet_name)
            settings.setValue("paths/bd_folder_path", bd_source)
            settings.setValue("paths/bd_excel_path", bd_excel)
            settings.setValue("paths/bd_sheet_name", bd_sheet)
            settings.setValue("paths/bd_json_path", bd_json)

            self.logger.info("设置已更新，数据已重新加载")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"重新加载数据失败: {str(e)}")
            self.logger.exception("重新加载数据失败")

if __name__ == "__main__":
    from src.Excel_Info import GetWriteInfo
    file_path = r"D:\Excel_Hander\excel\2025-05-19-竞彩"
    excel_path = r"D:\Excel_Hander\excel\副本5-19奥.xlsx"
    Eif = GetWriteInfo(file_path, excel_path)
    json_path = r"D:\Excel_Hander\dist\json\2025-05-19.json"
    # top_data = Eif.get_tabel_info()
    # files_names, excel_name = Eif.get_file_and_excel_info()
    app = QApplication(sys.argv)
    window = EnhancedDataEditor(excel_path=excel_path, file_path=file_path, json_path=json_path)
    window.show()
    sys.exit(app.exec_())