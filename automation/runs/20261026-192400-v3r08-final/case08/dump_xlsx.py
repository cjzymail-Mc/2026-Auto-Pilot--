# CASE-08：只读盘点公里统计表（openpyxl，无 COM），取精确单元格坐标供 locator 使用
import json, os
from openpyxl import load_workbook

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..'))
XLSX = os.path.join(REPO, 'feature01-细化报销skill', '12月公出-发票', '12月-自驾公出公里数统计表.xlsx')
book = load_workbook(XLSX, read_only=True, data_only=False)
for ws in book.worksheets:
    print('SHEET', repr(ws.title), ws.max_row, ws.max_column)
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 40)):
        cells = [(c.coordinate, c.value) for c in row if c.value is not None]
        if cells:
            print(cells)
book.close()
