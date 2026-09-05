from openpyxl import Workbook
from openpyxl.styles import Border, Side, Alignment, Font
from core.config import EMPLOYEES
from core.data_array import get_name_employee, is_settlement_allowed
from core.constants import MONTHS_NAME_TO_RUSSIAN


def build_excel(time_table: dict, work_time: dict, summary: dict, wages: dict) -> str:
    wb = Workbook()
    ws = wb.active
    _setup_columns(ws)
    _write_header(ws)
    _write_data_rows(ws, time_table, work_time)
    _write_summary_block(ws, work_time, summary, wages)
    ws.auto_filter.ref = 'A1:G24'
    list_dates = sorted(time_table.keys())
    month_num = int(list_dates[0][5:7])
    year_str = list_dates[0][:4]
    file_name = f'{MONTHS_NAME_TO_RUSSIAN[month_num]}_{year_str}.xlsx'
    wb.save(file_name)
    print(f'Файл {file_name} c общей таблицей сформирован')
    return file_name


def _setup_columns(ws) -> None:
    widths = {
        'A': 16.44, 'B': 13.48, 'C': 14.3, 'D': 16.43,
        'E': 20.84, 'F': 12.26, 'G': 13.23, 'H': 16.44,
        'I': 23.21, 'J': 12.46, 'K': 17.93, 'L': 21.96,
        'M': 28.09, 'N': 10.27, 'P': 10.3,
    }
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def _write_header(ws) -> None:
    border = _make_border()
    font = Font(name='Calibri', size=11, bold=True)
    topics = ['Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода',
              'Общее время работы', 'Переработка']
    for i, topic in enumerate(topics, 1):
        cell = ws.cell(column=i, row=1, value=topic)
        cell.font = font
        cell.border = border
    ws.merge_cells(start_row=1, start_column=6, end_row=1, end_column=7)
    ws.cell(column=6, row=1).alignment = Alignment(horizontal='center')


def _write_data_rows(ws, time_table: dict, work_time: dict) -> None:
    border = _make_border()
    count = 2
    for date_key in sorted(time_table.keys()):
        for emp_id in time_table[date_key]:
            if not is_settlement_allowed(emp_id):
                continue
            ws.cell(column=1, row=count, value=get_name_employee(emp_id)).border = border
            ws.cell(column=2, row=count, value=date_key).border = border
            marks = time_table[date_key][emp_id]
            tag = marks[2]
            if tag in ('work', 'weekend'):
                if date_key not in work_time or emp_id not in work_time[date_key]:
                    continue
                ws.cell(column=3, row=count, value=marks[1].time()).border = border
                ws.cell(column=4, row=count, value=marks[0].time()).border = border
                wd = work_time[date_key][emp_id]
                ws.cell(column=5, row=count, value=wd[1]).border = border
                ws.cell(column=7, row=count, value=wd[0]).border = border
                ws.cell(column=6, row=count, value=wd[2]).border = border
            elif tag == 'vacation':
                ws.cell(count, 3).border = border
                ws.merge_cells(start_row=count, start_column=3, end_row=count, end_column=7)
                ws.cell(column=3, row=count, value='Отпуск').alignment = Alignment(horizontal='center')
            elif tag == 'truancy':
                ws.cell(count, 3).border = border
                ws.merge_cells(start_row=count, start_column=3, end_row=count, end_column=7)
                ws.cell(column=3, row=count, value='Прогул').alignment = Alignment(horizontal='center')
            if is_settlement_allowed(emp_id):
                count += 1


def _write_summary_block(ws, work_time: dict, summary: dict, wages: dict) -> None:
    border = _make_border()
    max_row = 1
    for row in ws.iter_rows(min_row=2, max_col=1):
        if row[0].value:
            max_row = row[0].row
    count = max_row + 3
    topics = ['Фамилия', 'Отработано будних дней', 'Переработка', 'Рабочих выходных',
              'Переработка выходных', 'Количество дней отпуска', 'Оклад', 'Молоко', 'Зарплата']
    for i, topic in enumerate(topics, 8):
        ws.cell(column=i, row=count, value=topic).border = border
    count += 1
    for emp_id in summary:
        if not is_settlement_allowed(emp_id):
            continue
        ws.cell(column=8, row=count, value=get_name_employee(emp_id)).border = border
        ws.cell(column=9, row=count, value=summary[emp_id][0][0]).border = border
        ws.cell(column=9, row=count).alignment = Alignment(horizontal='center')
        ws.cell(column=10, row=count, value=summary[emp_id][0][1]).border = border
        ws.cell(column=11, row=count, value=summary[emp_id][1][0]).border = border
        ws.cell(column=11, row=count).alignment = Alignment(horizontal='center')
        ws.cell(column=12, row=count, value=summary[emp_id][1][1]).border = border
        ws.cell(column=13, row=count, value=summary[emp_id][2]).border = border
        ws.cell(column=13, row=count).alignment = Alignment(horizontal='center')
        if emp_id in wages:
            ws.cell(column=14, row=count, value=wages[emp_id][0]).border = border
            ws.cell(column=15, row=count, value=wages[emp_id][1]).border = border
            ws.cell(column=16, row=count, value=wages[emp_id][2]).border = border
        count += 1


def _make_border() -> Border:
    side = Side('thin', 'FF000000')
    return Border(left=side, right=side, top=side, bottom=side)
