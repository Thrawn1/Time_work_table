from openpyxl import Workbook
from openpyxl.styles import Border, Side, Alignment, Font
from core.config import EMPLOYEES
from core.data_array import get_name_employee, is_included_in_settlement
from core.constants import MONTHS_NAME_TO_RUSSIAN


def _set_cell(ws, row: int, column: int, value, border=None):
    """Записать ячейку; текстовые поля с =/+/-/@ — строго как строки (не формулы)."""
    cell = ws.cell(column=column, row=row, value=value)
    if border is not None:
        cell.border = border
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@'):
        # openpyxl иначе сохранит как формулу (data_type 'f')
        cell.data_type = 's'
    return cell


def build_excel(time_table: dict, work_time: dict, summary: dict, wages: dict,
                employees: dict | None = None) -> str:
    if not time_table:
        print('Нет данных для общей таблицы, Excel не создан.')
        return ''
    wb = Workbook()
    ws = wb.active
    _setup_columns(ws)
    _write_header(ws)
    last_detail_row = _write_data_rows(ws, time_table, work_time, employees)
    _write_summary_block(ws, work_time, summary, wages, employees)
    ws.auto_filter.ref = f'A1:G{max(last_detail_row, 1)}'
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


def _write_data_rows(ws, time_table: dict, work_time: dict,
                      employees: dict | None = None) -> int:
    """Записать детализацию. Возвращает последнюю строку детализации (>=1)."""
    from core.day_models import ATTENDANCE_TAGS, TAG_TRUANCY, TAG_VACATION

    border = _make_border()
    count = 2
    for date_key in sorted(time_table.keys()):
        for emp_id in time_table[date_key]:
            if not is_included_in_settlement(emp_id):
                continue
            marks = time_table[date_key][emp_id]
            tag = getattr(marks, 'tag', marks[2])
            if tag in ATTENDANCE_TAGS:
                if date_key not in work_time or emp_id not in work_time[date_key]:
                    continue
                _set_cell(ws, count, 1, get_name_employee(emp_id, employees), border)
                _set_cell(ws, count, 2, date_key, border)
                come = getattr(marks, 'come', marks[1])
                go = getattr(marks, 'go', marks[0])
                ws.cell(column=3, row=count, value=come.time()).border = border
                ws.cell(column=4, row=count, value=go.time()).border = border
                wd = work_time[date_key][emp_id]
                worked = getattr(wd, 'worked', wd[1])
                delta = getattr(wd, 'delta', wd[0])
                overtime_tag = getattr(wd, 'overtime_tag', wd[2])
                ws.cell(column=5, row=count, value=worked).border = border
                ws.cell(column=7, row=count, value=delta).border = border
                _set_cell(ws, count, 6, overtime_tag, border)
                count += 1
            elif tag in (TAG_VACATION, TAG_TRUANCY):
                _set_cell(ws, count, 1, get_name_employee(emp_id, employees), border)
                _set_cell(ws, count, 2, date_key, border)
                _set_cell(ws, count, 3, None, border)
                ws.merge_cells(start_row=count, start_column=3, end_row=count, end_column=7)
                label = 'Отпуск' if tag == TAG_VACATION else 'Прогул'
                _set_cell(ws, count, 3, label, None).alignment = Alignment(horizontal='center')
                ws.cell(column=3, row=count).border = border
                count += 1
            else:
                # Неизвестный тег: не выдумываем строку детализации.
                continue
    return count - 1


def _write_summary_block(ws, work_time: dict, summary: dict, wages: dict,
                         employees: dict | None = None) -> None:
    border = _make_border()
    max_row = 1
    for row in ws.iter_rows(min_row=2, max_col=1):
        if row[0].value:
            max_row = row[0].row
    count = max_row + 3
    topics = ['Фамилия', 'Отработано будних дней', 'Переработка', 'Недоработка',
              'Рабочих выходных', 'Переработка выходных', 'Количество дней отпуска',
              'Оклад', 'Молоко', 'Зарплата']
    for i, topic in enumerate(topics, 8):
        ws.cell(column=i, row=count, value=topic).border = border
    count += 1
    for emp_id in summary:
        if not is_included_in_settlement(emp_id):
            continue
        _set_cell(ws, count, 8, get_name_employee(emp_id, employees), border)
        entry = summary[emp_id]
        work = getattr(entry, 'work', entry[0])
        holiday = getattr(entry, 'holiday', entry[1])
        ws.cell(column=9, row=count, value=getattr(work, 'days', work[0])).border = border
        ws.cell(column=9, row=count).alignment = Alignment(horizontal='center')
        ws.cell(column=10, row=count, value=getattr(work, 'overtime', work[1])).border = border
        ws.cell(column=11, row=count, value=getattr(work, 'undertime', work[2])).border = border
        ws.cell(column=12, row=count, value=getattr(holiday, 'days', holiday[0])).border = border
        ws.cell(column=12, row=count).alignment = Alignment(horizontal='center')
        ws.cell(column=13, row=count, value=getattr(holiday, 'overtime', holiday[1])).border = border
        ws.cell(column=14, row=count, value=getattr(entry, 'vacation_days', entry[2])).border = border
        ws.cell(column=14, row=count).alignment = Alignment(horizontal='center')
        if emp_id in wages:
            wage = wages[emp_id]
            vals = (
                getattr(wage, 'salary', wage[0]),
                getattr(wage, 'milk', wage[1]),
                getattr(wage, 'total_with_milk', wage[2]),
            )
            for col, val in ((15, vals[0]), (16, vals[1]), (17, vals[2])):
                cell = ws.cell(column=col, row=count, value=val)
                cell.border = border
                cell.number_format = '0.00'
        count += 1


def _make_border() -> Border:
    side = Side('thin', 'FF000000')
    return Border(left=side, right=side, top=side, bottom=side)
