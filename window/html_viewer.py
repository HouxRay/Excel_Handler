"""HTML 查看器窗口 — 内嵌 WebEngine 查看 HTML 文件，支持星期高亮"""
from pathlib import Path
from datetime import datetime, timezone, timedelta

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                             QComboBox, QLabel, QWidget, QMessageBox, QPushButton)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt, QUrl


class NewWindow(QDialog):
    def __init__(self, selected_item, html_base_path, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        try:
            self.setWindowTitle(f"HTML查看器 - {selected_item}")
            self.setGeometry(0, 0, 1100, 800)

            self.html_base_path = Path(html_base_path)
            self.weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

            beijing_tz = timezone(timedelta(hours=8))
            current_weekday = datetime.now(beijing_tz).weekday()
            self.default_day = self.weekday_names[current_weekday]
            self.current_day = self.default_day

            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            toolbar_widget = QWidget()
            toolbar_widget.setMaximumHeight(28)
            toolbar_widget.setStyleSheet("background-color: #f5f5f5; border-bottom: 1px solid #ddd;")
            toolbar_layout = QHBoxLayout(toolbar_widget)
            toolbar_layout.setContentsMargins(4, 1, 4, 1)
            toolbar_layout.setSpacing(3)
            toolbar_layout.addWidget(QLabel("高亮:"))
            self.day_combo = QComboBox()
            self.day_combo.setMaximumWidth(80)
            self.day_combo.setStyleSheet("font-size: 11px;")
            self.day_combo.addItems(self.weekday_names)
            idx = self.weekday_names.index(self.default_day)
            self.day_combo.setCurrentIndex(idx)
            self.day_combo.currentTextChanged.connect(self._on_day_changed)
            toolbar_layout.addWidget(self.day_combo)

            # AI 分析按钮：分析当前打开的 HTML
            self.ai_btn = QPushButton("🤖 AI 分析当前内容")
            self.ai_btn.setStyleSheet("font-size: 11px; padding: 1px 6px;")
            self.ai_btn.clicked.connect(self._on_ai_fill)
            toolbar_layout.addWidget(self.ai_btn)

            toolbar_layout.addStretch()
            layout.addWidget(toolbar_widget)

            self.web_view = QWebEngineView()
            if self.html_base_path.exists():
                self.web_view.load(QUrl.fromLocalFile(str(self.html_base_path)))
            else:
                self.web_view.setHtml(f"<h1>文件未找到</h1><p>{self.html_base_path}</p>")
            self.web_view.loadFinished.connect(self._inject_highlight)
            layout.addWidget(self.web_view)
            self.setLayout(layout)

        except Exception as e:
            QMessageBox.warning(self, "错误", "当前HTML文件路径错误，请检查！")

    def _on_ai_fill(self):
        """AI 分析当前打开的 HTML 文件，结果填入主窗口"""
        parent = self.parent()
        if parent is None or not hasattr(parent, '_ai_fill_from_html'):
            QMessageBox.warning(self, "提示", "无法获取主窗口")
            return
        parent._ai_fill_from_html(str(self.html_base_path))

    def closeEvent(self, event):
        if hasattr(self, 'web_view'):
            self.web_view.setPage(None)
            self.web_view.stop()
            self.web_view = None
        super().closeEvent(event)

    def _on_day_changed(self, day_text):
        self.current_day = day_text
        self._inject_highlight()

    def _inject_highlight(self, ok=True):
        if not ok:
            return
        js_code = f"""
        (function() {{
            var oldSpans = document.querySelectorAll('.weekday-highlight');
            for (var i = 0; i < oldSpans.length; i++) {{
                var parent = oldSpans[i].parentNode;
                var txt = document.createTextNode(oldSpans[i].textContent);
                parent.replaceChild(txt, oldSpans[i]);
                parent.normalize();
            }}
            var target = "{self.current_day}";
            if (!target) return;
            var walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT, null, false
            );
            var nodes = [];
            while (walker.nextNode()) nodes.push(walker.currentNode);
            for (var i = 0; i < nodes.length; i++) {{
                var node = nodes[i];
                if (node.textContent.indexOf(target) !== -1) {{
                    var span = document.createElement('span');
                    span.className = 'weekday-highlight';
                    span.style.backgroundColor = 'yellow';
                    span.style.color = 'red';
                    span.style.fontWeight = 'bold';
                    span.textContent = node.textContent;
                    node.parentNode.replaceChild(span, node);
                }}
            }}
        }})();
        """
        self.web_view.page().runJavaScript(js_code)
