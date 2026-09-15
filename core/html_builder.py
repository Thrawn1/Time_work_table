from datetime import timedelta
import html
import re
from core.config import EMPLOYEES
from core.data_array import get_name_employee, is_settlement_allowed
from core.constants import MONTHS_NAME_TO_RUSSIAN
from core.calculations import str_timedelta
from core.money import format_money


def sanitize_filename_part(text: str) -> str:
    """Убрать запрещённые в Windows символы <>:\"/\\|?* и управляющие."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', text or '').strip()
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned or 'ID'


def build_html(emp_id: int, time_table: dict, work_time: dict, summary: dict, wages: dict,
               employees: dict | None = None, bundle=None) -> str:
    """Персональный отчет + (при bundle) прозрачный блок новой модели.

    bundle=None — legacy-режим без изменений. При bundle добавляется общий
    заголовок (база/D/ставки) и строка оснований именно этого сотрудника.
    """
    family = get_name_employee(emp_id, employees)
    daily_data = _build_daily_data(emp_id, time_table, work_time, employees)
    if not daily_data:
        print(f'Пропущен {family or emp_id}: нет отметок за период, HTML не создан.')
        return ''
    if emp_id not in summary or emp_id not in wages:
        print(f'Пропущен {family or emp_id}: нет данных расчета (роль не поддерживается?), HTML не создан.')
        return ''
    total_data = _build_total_data(emp_id, summary, wages, employees)
    month_num = daily_data[0]['date'][5:7]
    year_str = daily_data[0]['date'][:4]
    safe_family = sanitize_filename_part(family or f'ID_{emp_id}')
    file_name = f'{safe_family}_{emp_id}_{month_num}_{year_str}.html'
    pay_lines = _gen_pay_section(emp_id, bundle) if bundle is not None else []
    _write_html_file(file_name, daily_data, total_data, pay_lines)
    print(f'Файл готов: {file_name}')
    return file_name


def _build_daily_data(emp_id: int, time_table: dict, work_time: dict,
                      employees: dict | None = None) -> list[dict]:
    from core.day_models import TAG_TRUANCY, TAG_VACATION

    if employees is None:
        from core.config import EMPLOYEES as _fallback

        staff = _fallback
    else:
        staff = employees
    all_ids = {eid: get_name_employee(eid, staff) for eid in staff}
    dates = sorted(time_table.keys())
    result = []
    for date_key in dates:
        if emp_id in time_table[date_key]:
            marks = time_table[date_key][emp_id]
            if date_key not in work_time or emp_id not in work_time[date_key]:
                continue
            wd = work_time[date_key][emp_id]
            tag = getattr(marks, 'tag', marks[2])
            come = getattr(marks, 'come', marks[1])
            go = getattr(marks, 'go', marks[0])
            worked = getattr(wd, 'worked', wd[1])
            overtime_tag = getattr(wd, 'overtime_tag', wd[2])
            delta = getattr(wd, 'delta', wd[0])
            entry = {
                'family': all_ids.get(emp_id, ''),
                'date': date_key,
                'time_begin': come.time().isoformat(timespec='auto'),
                'time_end': go.time().isoformat(timespec='auto'),
                'delta_time': str(worked),
                'tag_overtime': overtime_tag,
                'overtime': str(delta),
                'tag_day': tag,
            }
            if tag == TAG_VACATION:
                entry['tag_day'] = 'Отпуск'
            elif tag == TAG_TRUANCY:
                entry['tag_day'] = 'Прогул'
            result.append(entry)
    return result


def _build_total_data(emp_id: int, summary: dict, wages: dict,
                      employees: dict | None = None) -> dict:
    data = summary[emp_id]
    work = getattr(data, 'work', data[0])
    holiday = getattr(data, 'holiday', data[1])
    wage = wages[emp_id]
    return {
        'family': get_name_employee(emp_id, employees),
        'all_work_weekdays': getattr(work, 'days', work[0]),
        'weekdays_overtime': str_timedelta(getattr(work, 'overtime', work[1])),
        'weekdays_undertime': str_timedelta(getattr(work, 'undertime', work[2])),
        'work_weekend': getattr(holiday, 'days', holiday[0]),
        'overtime_weekend': str_timedelta(getattr(holiday, 'overtime', holiday[1])),
        'vacation': getattr(data, 'vacation_days', data[2]),
        'salary': format_money(getattr(wage, 'salary', wage[0])),
        'milk': format_money(getattr(wage, 'milk', wage[1])),
        'salary_whith_milk': format_money(getattr(wage, 'total_with_milk', wage[2])),
    }


def _write_html_file(file_name: str, daily_data: list[dict], total_data: dict,
                     pay_lines: list[str] | None = None) -> None:
    lines = ['<html>\n']
    lines.append('  <table border="5" class="dataframe" style="width:100%">\n')
    lines.extend(_gen_header(1))
    lines.append('    <tbody>\n')
    lines.append('      <tr>\n')
    for day in daily_data:
        lines.extend(_gen_day_row(day))
    lines.append('      </tr>\n')
    lines.append('    </tbody>\n')
    lines.append('  </table>\n')
    lines.append('  <table border="5" class="dataframe" style="width:100%">\n')
    lines.extend(_gen_header(2))
    lines.append('    <tbody>\n')
    lines.append('      <tr>\n')
    lines.extend(_gen_total_row(total_data))
    lines.append('      </tr>\n')
    lines.append('    </tbody>\n')
    lines.append('  </table>\n')
    if pay_lines:
        lines.extend(pay_lines)
    lines.append('</html>\n')
    with open(file_name, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def _pay_header_text(bundle) -> str:
    """Тот же заголовок, что в консоли/Excel: база, D, ставки, условия."""
    from core.payroll import pay_header_text

    return pay_header_text(bundle)


def _gen_pay_section(emp_id: int, bundle) -> list[str]:
    """Блок новой модели для персонального HTML: заголовок + строка сотрудника."""
    from core.money import format_money

    lines = ['  <h3>Новая модель оплаты</h3>\n']
    lines.append(f'  <p>{html.escape(_pay_header_text(bundle), quote=True)}</p>\n')
    r = bundle.results.get(emp_id)
    if r is None:
        lines.append('  <p>Сотрудник не входит в ведомость новой модели.</p>\n')
        return lines
    res = r.result
    lines.append('  <table border="5" class="dataframe" style="width:100%">\n')
    topics = ['Сотрудник', 'Норма/факт, ч', 'Обычная, ₽',
              'Переработка', 'Полный месяц', 'Причина', 'Стаж', 'Итого, ₽']
    lines.append('    <thead>\n      <tr style="text-align: center;">\n')
    for t in topics:
        lines.append(f'        <th>{html.escape(t, quote=True)}</th>\n')
    lines.append('      </tr>\n    </thead>\n')
    lines.append('    <tbody>\n      <tr>\n')
    cells = [
        r.name,
        f'{res.norm_hours}/{res.fact_hours}',
        format_money(res.ordinary_pay),
        f'{res.overtime_hours} ч / {format_money(res.overtime_bonus)}',
        f"{'+' if res.full_month_ok else '-'} / {format_money(res.full_month_bonus)}",
        res.full_month_reason,
        f'{res.seniority_rate * 100}% / {format_money(res.seniority_bonus)}',
        format_money(res.total),
    ]
    for c in cells:
        lines.append(f'        <td>{html.escape(str(c), quote=True)}</td>\n')
    lines.append('      </tr>\n    </tbody>\n  </table>\n')
    for w in bundle.warnings:
        lines.append(f'  <p>ВНИМАНИЕ: {html.escape(str(w), quote=True)}</p>\n')
    return lines


def _gen_header(table_type: int) -> list[str]:
    if table_type == 1:
        topics = ['Фамилия', 'Дата', 'Отметка входа', 'Отметка выхода',
                  'Общее время работы', 'Переработка']
    else:
        topics = ['Фамилия', 'Отработано будних дней', 'Переработка в будние дни',
                  'Недоработка в будние дни', 'Рабочих выходных', 'Переработка в выходные дни',
                  'Количество дней отпуска', 'Оклад', 'Молоко', 'Зарплата']
    lines = ['    <thead>\n', '      <tr style="text-align: center;">\n']
    for t in topics:
        if t == 'Переработка':
            lines.append(f'        <th colspan="2" align="center">{t}</th>\n')
        else:
            lines.append(f'        <th>{t}</th>\n')
    lines.append('      </tr>\n')
    lines.append('    </thead>\n')
    return lines


def _gen_day_row(day: dict) -> list[str]:
    from core.day_models import ATTENDANCE_TAGS

    tag = day['tag_day']
    family = html.escape(str(day.get('family', '')), quote=True)
    date = html.escape(str(day.get('date', '')), quote=True)
    row = [f'        <tr>\n']
    row.append(f'          <td>{family}</td>\n')
    row.append(f'          <td>{date}</td>\n')
    if tag in ATTENDANCE_TAGS:
        time_begin = html.escape(str(day.get('time_begin', '')), quote=True)
        time_end = html.escape(str(day.get('time_end', '')), quote=True)
        delta = html.escape(str(day.get('delta_time', '')), quote=True)
        tag_over = html.escape(str(day.get('tag_overtime', '')), quote=True)
        overtime = html.escape(str(day.get('overtime', '')), quote=True)
        row.append(f'          <td>{time_begin}</td>\n')
        row.append(f'          <td>{time_end}</td>\n')
        row.append(f'          <td>{delta}</td>\n')
        row.append(f'          <td>{tag_over}</td>\n')
        row.append(f'          <td>{overtime}</td>\n')
    else:
        tag_esc = html.escape(str(tag), quote=True)
        row.append(f'          <td colspan="5" align="center">{tag_esc}</td>\n')
    row.append('        </tr>\n')
    return row


def _gen_total_row(total: dict) -> list[str]:
    def esc(v) -> str:
        return html.escape(str(v), quote=True)

    row = ['        <tr>\n']
    row.append(f'          <th align="center">{esc(total.get("family", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("all_work_weekdays", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("weekdays_overtime", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("weekdays_undertime", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("work_weekend", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("overtime_weekend", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("vacation", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("salary", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("milk", ""))}</th>\n')
    row.append(f'          <th>{esc(total.get("salary_whith_milk", ""))}</th>\n')
    row.append('        </tr>\n')
    return row

