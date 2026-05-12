# -*- coding: utf-8 -*-
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from PyQt5.QtWidgets import QApplication
app = QApplication(sys.argv)

from src.Excel_Info import GetWriteInfo

eif = GetWriteInfo("test_excel/2026-05-12-jc", "test_excel/副本5-12.xlsx")
_, excel_first_columns = eif.get_file_and_excel_info()

print("ALL Excel first column entries:")
for name, row in sorted(excel_first_columns.items(), key=lambda x: x[1]):
    print(f"  row {row}: {name}")

# Search for pic categories
print("\nSearching for pic categories...")
for target in ['白', '鸿运', '植树', '手写', '彩虹', '色']:
    matches = [(n, r) for n, r in excel_first_columns.items() if target in n]
    if matches:
        print(f"  '{target}' found: {matches}")
    else:
        print(f"  '{target}': NOT FOUND")
