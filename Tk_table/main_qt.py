import sys
from PyQt5.QtWidgets import QApplication
from src.Excel_Info import GetWriteInfo
from Tk_table.main_window import EnhancedDataEditor


if __name__ == "__main__":
    Eif = GetWriteInfo("src\\2025-03-03-竞彩", "src\sample.xlsx")
    app = QApplication(sys.argv)
    window = EnhancedDataEditor(Eif.get_tabel_info(), Eif.get_file_and_excel_info()[0])
    window.show()
    sys.exit(app.exec_())
