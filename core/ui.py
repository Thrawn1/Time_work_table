"""Консольный UI на rich с fallback на обычный print.

Правило: вся красивость — только здесь. Расчетные модули возвращают данные,
а не печатают. Если rich не установлен — те же функции печатают plain-текст.
"""

from __future__ import annotations

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    HAS_RICH = True
except ImportError:  # pragma: no cover - fallback проверяется без rich
    Console = None  # type: ignore
    Table = None  # type: ignore
    Panel = None  # type: ignore
    HAS_RICH = False

_console = None


def get_console():
    """Синглтон консоли rich (или None при fallback)."""
    global _console
    if not HAS_RICH:
        return None
    if _console is None:
        _console = Console()
    return _console


def summarize_employee(single_count: int, missed_count: int, has_marks: bool) -> dict:
    """Чистый статус сотрудника для дашборда.

    Возвращает {'status': str, 'style': str} где style — цвет rich.
    """
    if not has_marks:
        return {'status': 'Нет данных', 'style': 'red'}
    if single_count == 0 and missed_count == 0:
        return {'status': 'OK', 'style': 'green'}
    return {'status': 'Править', 'style': 'yellow'}


def build_dashboard_rows(time_table: dict, emp_ids: list[int], year: int, month: int,
                         employees: dict | None = None,
                         extra_excluded: dict | None = None,
                         rules_by_role: dict | None = None,
                         included_ids: set[int] | None = None) -> list[dict]:
    """Собрать строки дашборда. Чистая агрегация, без печати.

    extra_excluded: {emp_id: причина} из SQLite (participates=False,
    персональные исключения) — объединяется с DAT-причиной, чтобы дашборд
    показывал единый состав с bundle (F02). rules_by_role — действующие
    SQLite-правила (R01–R02). included_ids — окончательные участники расчёта:
    сотрудник без отметок, но включённый через --include-empty, помечается
    «Включён без отметок», а не «в расчёт не включён» (R07).
    """
    from core.analysis import _current_average, _get_marks_and_missed
    from core.config import MANUAL_EXCLUSIONS

    if employees is None:
        from core.config import EMPLOYEES as _fallback

        staff = _fallback
    else:
        staff = employees
    rows: list[dict] = []
    for emp_id in emp_ids:
        role = staff.get(emp_id) if hasattr(staff, 'get') else None
        name = f'{role.last_name} {role.first_name}'.strip() if role else f'ID {emp_id}'
        has_marks = any(emp_id in day for day in time_table.values())
        list_marks, list_missed = _get_marks_and_missed(
            time_table, emp_id, year, month,
            employees=staff, rules_by_role=rules_by_role)
        single_count = len(list_marks) if isinstance(list_marks, list) else 0
        missed_count = len(list_missed) if isinstance(list_missed, list) else 0
        included = included_ids is not None and emp_id in included_ids
        info = summarize_employee(single_count, missed_count, has_marks or included)
        # R07: включённый без отметок — отдельный статус, а не «не включён».
        if included and not has_marks:
            info = {'status': 'Включён без отметок', 'style': 'cyan'}
        from core.data_array import exclusion_reason
        reason = exclusion_reason(emp_id, staff)
        rules_reason = exclusion_reason(emp_id, staff, include_manual=False)
        if extra_excluded and emp_id in extra_excluded:
            _sqlite_reason = extra_excluded[emp_id] or 'исключён SQLite'
            if not reason:
                reason = _sqlite_reason
            elif _sqlite_reason not in reason:  # одна и та же причина из DAT и SQLite — один раз
                reason = f'{reason}; {_sqlite_reason}'
            rules_reason = rules_reason or _sqlite_reason
        avg = _current_average(time_table, emp_id)
        rows.append({
            'emp_id': emp_id,
            'name': name,
            'single': single_count,
            'missed': missed_count,
            'has_marks': has_marks,
            'included_without_marks': bool(included and not has_marks),
            'status': info['status'],
            'style': info['style'],
            'excluded': reason != '',
            'reason': reason,
            # Исключён оператором на этом запуске (и справочники его не исключают).
            'manual': emp_id in MANUAL_EXCLUSIONS and not rules_reason,
            'avg_come': avg.come_text if avg else None,
            'avg_go': avg.go_text if avg else None,
            'avg_days': avg.days if avg else 0,
        })
    return rows


def review_numbering(rows: list[dict]) -> list[dict]:
    """Строки, доступные по номеру: участники расчёта и исключённые вручную.

    Номер строки = индекс в этом списке + 1, порядок — как в справочнике. Он не
    зависит от того, исключён ли сотрудник: номер не «уезжает» после `x<номер>`,
    а вернуть исключённого можно по тому же номеру, что показан в блоке исключённых.
    """
    return [r for r in rows
            if ((r['has_marks'] or r.get('included_without_marks')) and not r.get('excluded'))
            or (r.get('manual') and r['has_marks'])]


def build_repairmen_lines(time_table: dict, employees: dict, year: int, month: int) -> list[str]:
    """«Максим Смирнов — 12, 15, 18, 25 сентября» для каждого ремонтника.

    Чистая функция без печати. Ремонтники — роль REPAIRMEN_ROLE_ID, без начислений:
    на экране только дни выходов за месяц. Нет выходов — «выходов нет».
    """
    from core.constants import MONTHS_NAME_GENITIVE
    from core.roles import REPAIRMEN_ROLE_ID

    prefix = f'{year:04d}-{month:02d}-'
    month_ru = MONTHS_NAME_GENITIVE.get(month, str(month)).lower()
    items: list[tuple[str, list[int]]] = []
    for emp_id, emp in (employees or {}).items():
        if getattr(emp, 'role_id', None) != REPAIRMEN_ROLE_ID:
            continue
        days = sorted(int(date_key[8:10]) for date_key, day in time_table.items()
                      if date_key.startswith(prefix) and emp_id in day)
        name = f'{emp.first_name} {emp.last_name}'.strip() or f'ID {emp_id}'
        items.append((name, days))
    items.sort(key=lambda item: item[0])
    return [f'{name} — {", ".join(str(d) for d in days)} {month_ru}' if days
            else f'{name} — выходов нет' for name, days in items]


def print_repairmen(lines: list[str], title: str = 'Ремонтники (выходы, без начислений)') -> None:
    """Список ремонтников: по строке на человека. Пустой список — ничего не печатаем."""
    if not lines:
        return
    if not HAS_RICH:
        print(f'=== {title} ===')
        for line in lines:
            print(line)
        return
    get_console().print(Panel('\n'.join(lines), title=title, border_style='blue'))


def print_dashboard(rows: list[dict], title: str = 'Сводка', numbered: bool = False) -> None:
    """Дашборд блоками: в расчёте / включён без отметок / без отметок / исключён.

    R07/R19: явно различаем «исключён», «нет данных» и «включён без отметок»
    (--include-empty). Сотрудники без единой отметки вне расчёта не смешиваются
    с проблемами действующих. По каждому участнику: сколько дней с одной меткой,
    сколько рабочих дней вообще без меток и среднее время прихода/ухода.
    numbered=True — добавить номера для меню разбора (см. review_numbering);
    исключённые вручную тоже получают номер, чтобы их можно было вернуть.
    """
    active = [r for r in rows
              if (r['has_marks'] or r.get('included_without_marks')) and not r.get('excluded')]
    inactive = [r for r in rows
                if not r['has_marks'] and not r.get('included_without_marks')
                and not r.get('excluded')]
    excluded = [r for r in rows if r.get('excluded')]
    numbers = {r['emp_id']: n for n, r in enumerate(review_numbering(rows), 1)} if numbered else {}

    def _label(r: dict) -> str:
        return f"{numbers[r['emp_id']]}. {r['name']}" if r['emp_id'] in numbers else r['name']

    def _avg(r: dict, key: str) -> str:
        return r.get(key) or '—'

    if not HAS_RICH:
        print(f'=== {title}: в расчете ({len(active)}) ===')
        for r in active:
            print(f"{_label(r)}: одна метка={r['single']} нет меток={r['missed']} "
                  f"ср. приход={_avg(r, 'avg_come')} ср. уход={_avg(r, 'avg_go')} [{r['status']}]")
        print(f'--- Без отметок за месяц ({len(inactive)}): в расчет не включены ---')
        for r in inactive:
            print(f"{r['name']} [Нет данных]")
        print(f'--- Исключены из начислений ({len(excluded)}) ---')
        for r in excluded:
            print(f"{_label(r)} [{r.get('reason', 'исключён')}]")
        return
    console = get_console()
    table = Table(title=f'{title}: в расчете ({len(active)})')
    if numbered:
        table.add_column('№', justify='right')
    table.add_column('Сотрудник')
    table.add_column('Одна метка', justify='right')
    table.add_column('Нет меток', justify='right')
    table.add_column('Ср. приход', justify='right')
    table.add_column('Ср. уход', justify='right')
    table.add_column('Статус', justify='center')
    for r in active:
        cells = [r['name'], str(r['single']), str(r['missed']),
                 _avg(r, 'avg_come'), _avg(r, 'avg_go'),
                 f"[{r['style']}]{r['status']}[/{r['style']}]"]
        if numbered:
            cells.insert(0, str(numbers[r['emp_id']]))
        table.add_row(*cells)
    console.print(table)
    if inactive:
        names = ', '.join(r['name'] for r in inactive)
        console.print(f'[dim]Без отметок за месяц ({len(inactive)}), '
                      f'в расчет не включены: {names}[/dim]')
    if excluded:
        names = ', '.join(f"{_label(r)} ({r.get('reason', 'исключён')})" for r in excluded)
        console.print(f'[red]Исключены из начислений ({len(excluded)}): {names}[/red]')


def print_header(title: str) -> None:
    """Заголовок стадии."""
    if not HAS_RICH:
        print(f'=== {title} ===')
        return
    get_console().rule(title)


def info(msg: str, markup: bool = True) -> None:
    """Обычное сообщение. markup=False — печатать как есть: `[a]` не должно
    читаться rich как тег стиля и пропадать из подсказки меню."""
    if not HAS_RICH:
        print(msg)
        return
    get_console().print(msg, markup=markup)


def warn(msg: str) -> None:
    """Предупреждение (желтое при rich)."""
    if not HAS_RICH:
        print(msg)
        return
    get_console().print(f'[yellow]{msg}[/yellow]')


def error(msg: str) -> None:
    """Ошибка (красная при rich)."""
    if not HAS_RICH:
        print(msg)
        return
    get_console().print(f'[red]{msg}[/red]')


def ask_menu(prompt: str, valid: tuple[str, ...], cancel_tokens: tuple[str, ...] = ('0', 'q', 'отмена')) -> str:
    """Запросить пункт меню до валидного. Возвращает выбор как есть.

    Ввод — через builtins input (мокается в тестах), оформление — через rich.
    cancel_tokens считаются валидным выбором «пропустить».
    """
    allowed = tuple(valid) + tuple(cancel_tokens)
    while True:
        try:
            raw = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return cancel_tokens[0] if cancel_tokens else '0'
        if raw in allowed:
            return raw
        info(f'Введите один из: {", ".join(allowed)}.')


def confirm_save(preview: str) -> bool:
    """Подтверждение сохранения. True — сохранить, False — ввести заново."""
    while True:
        try:
            raw = input(f'{preview}\nПодтвердить? [д/н]: ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        if raw in ('д', 'y', 'да', 'yes', '1'):
            return True
        if raw in ('н', 'n', 'нет', 'no', '0'):
            return False
        info('Введите "д" или "н".')


def print_day_card_single(name: str, date_key: str, existing, avg_hint: str | None = None) -> None:
    """Карточка одиночной отметки (avg_hint — строка о среднем времени сотрудника)."""
    body = (f'Сотрудник: {name}\n'
            f'Дата: {date_key}\n'
            f'Сохранено: {existing}\n'
            + (f'{avg_hint}\n' if avg_hint else '')
            + '[1] приход  [2] уход  [3] авто по среднему (± 5 мин)  [0] пропустить')
    if not HAS_RICH:
        print(body)
        return
    get_console().print(Panel(body, title='Одиночная отметка', border_style='yellow'))


def print_missed_day_card(name: str, missed_day: str, avg_hint: str | None = None) -> None:
    """Карточка пропущенного дня (avg_hint — строка о среднем времени сотрудника)."""
    body = (f'Сотрудник: {name}\n'
            f'Дата без отметок: {missed_day}\n'
            + (f'{avg_hint}\n' if avg_hint else '')
            + '[1] рабочий день  [2] отпуск  [3] прогул  [5] больничный  '
              '[6] авто по среднему (± 5 мин)  [0] пропустить')
    if not HAS_RICH:
        print(body)
        return
    get_console().print(Panel(body, title='Нет данных за день', border_style='red'))


def build_start_info(file: str, year: int, month: int, rows_read: int,
                     employees_total: int, session_state: str,
                     output_dir: str = 'result', data_dir: str = 'data') -> dict:
    """Чистые данные стартового экрана. session_state: resumed|ignored|none|fresh."""
    labels = {
        'resumed': 'сессия восстановлена (--resume)',
        'ignored': 'найденная сессия проигнорирована (без --resume)',
        'none': 'сессии не было',
        'fresh': 'новый расчет',
    }
    return {
        'file': file,
        'year': year,
        'month': month,
        'rows_read': rows_read,
        'employees_total': employees_total,
        'session_state': session_state,
        'session_label': labels.get(session_state, session_state),
        'output_dir': output_dir,
        'data_dir': data_dir,
    }


def print_start_screen(info: dict) -> None:
    """Стартовый экран: источник, период, объем, сессия, каталоги."""
    lines = (f"Файл: {info['file']}\n"
             f"Период: {info['month']:02d}.{info['year']}\n"
             f"Строк данных: {info['rows_read']}\n"
             f"Сотрудников в расчете: {info['employees_total']}\n"
             f"Сессия: {info['session_label']}\n"
             f"Данные: {info.get('data_dir', 'data')}\n"
             f"Результаты: {info.get('output_dir', 'result')}")
    if not HAS_RICH:
        print('=== Старт ===')
        print(lines)
        return
    get_console().print(Panel(lines, title='Старт расчета', border_style='cyan'))


def print_pay_details(bundle) -> None:
    """Прозрачная ведомость новой модели: база, D, ставки, основания бонусов.

    Все представления используют один результат расчёта (bundle) —
    собственных формул здесь нет, только отображение.
    """
    from core.money import format_money
    from core.payroll import pay_header_text

    header = pay_header_text(bundle)
    if not bundle.results:
        info(header)
        return
    if not HAS_RICH:
        print(header)
        for r in bundle.results.values():
            res = r.result
            print(f"{r.name}: норма {res.norm_hours} ч, факт {res.fact_hours} ч, "
                  f"обычная {format_money(res.ordinary_pay)}, "
                  f"переработка {res.overtime_hours} ч -> {format_money(res.overtime_bonus)}, "
                  f"полный месяц {'+' if res.full_month_ok else '-'} "
                  f"({res.full_month_reason}) -> {format_money(res.full_month_bonus)}, "
                  f"стаж {res.seniority_rate * 100}% от {format_money(res.seniority_basis_exact)} "
                  f"-> {format_money(res.seniority_bonus)}, "
                  f"ИТОГО {format_money(res.total)}")
        for w in bundle.warnings:
            print(f'ВНИМАНИЕ: {w}')
        return
    console = get_console()
    console.print(header)
    table = Table(title='Ведомость (новая модель)')
    for col in ('Сотрудник', 'Норма/факт, ч', 'Обычная', 'Переработка', 'Полный мес.',
                'Причина', 'Стаж', 'Итого'):
        table.add_column(col, justify='right' if col != 'Сотрудник' else 'left')
    for r in bundle.results.values():
        res = r.result
        table.add_row(
            r.name,
            f'{res.norm_hours}/{res.fact_hours}',
            format_money(res.ordinary_pay),
            f'{res.overtime_hours} ч / {format_money(res.overtime_bonus)}',
            f"{'+' if res.full_month_ok else '-'} / {format_money(res.full_month_bonus)}",
            res.full_month_reason,
            f'{res.seniority_rate * 100}% / {format_money(res.seniority_bonus)}',
            format_money(res.total),
        )
    console.print(table)
    for w in bundle.warnings:
        console.print(f'[yellow]ВНИМАНИЕ: {w}[/yellow]')


def build_preview_rows(summary: dict, wages: dict, employees: dict | None = None,
                        bundle=None) -> list[dict]:
    """Чистые строки предпросмотра расчета до записи файлов.

    При bundle (новая модель) показываем только его участников:
    emp вне bundle.results пропускается, а не выводится с нулевой зарплатой (F02).
    """
    from core.calculations import str_timedelta
    from core.data_array import is_settlement_allowed
    from core.day_models import WageResult
    from core.money import as_decimal
    from decimal import Decimal

    if employees is None:
        from core.config import EMPLOYEES as _fallback

        staff = _fallback
    else:
        staff = employees
    rows: list[dict] = []
    for emp_id, data in summary.items():
        if not is_settlement_allowed(emp_id):
            continue
        if bundle is not None and emp_id not in bundle.results:
            continue
        role = staff.get(emp_id) if hasattr(staff, 'get') else None
        name = f'{role.last_name} {role.first_name}'.strip() if role else f'ID {emp_id}'
        wage = wages.get(emp_id, WageResult(Decimal('0.00'), Decimal('0.00'), Decimal('0.00')))
        salary = getattr(wage, 'salary', wage[0])
        milk = getattr(wage, 'milk', wage[1])
        total = getattr(wage, 'total_with_milk', wage[2])
        work = getattr(data, 'work', data[0])
        holiday = getattr(data, 'holiday', data[1])
        work_days = getattr(work, 'days', work[0])
        overtime = getattr(work, 'overtime', work[1])
        undertime = getattr(work, 'undertime', work[2])
        weekend_days = getattr(holiday, 'days', holiday[0])
        vacation = getattr(data, 'vacation_days', data[2])
        rows.append({
            'emp_id': emp_id,
            'name': name,
            'work': work_days,
            'overtime': str_timedelta(overtime),
            'undertime': str_timedelta(undertime),
            'weekend': weekend_days,
            'vacation': vacation,
            'salary': as_decimal(salary),
            'milk': as_decimal(milk),
            'total': as_decimal(total),
        })
    return sorted(rows, key=lambda r: r['name'])


def print_preview(rows: list[dict], title: str = 'Предпросмотр расчета') -> None:
    """Таблица предпросмотра до записи файлов.

    Длительности — str_timedelta (HH:MM:SS), деньги — format_money (HALF_UP),
    как в Excel/HTML (F22.6).
    """
    from core.money import format_money

    if not HAS_RICH:
        print(f'=== {title} ===')
        for r in rows:
            print(f"{r['name']}: будни={r['work']} (+{r['overtime']}/-{r['undertime']}) "
                  f"вых={r['weekend']} отп={r['vacation']} итого={format_money(r['total'])}")
        return
    console = get_console()
    table = Table(title=title)
    table.add_column('Сотрудник')
    table.add_column('Будни', justify='right')
    table.add_column('Перераб', justify='right')
    table.add_column('Недораб', justify='right')
    table.add_column('Выходные', justify='right')
    table.add_column('Отпуск', justify='right')
    table.add_column('Итого', justify='right')
    for r in rows:
        table.add_row(
            r['name'], str(r['work']), r['overtime'], r['undertime'],
            str(r['weekend']), str(r['vacation']), format_money(r['total']),
        )
    console.print(table)


def print_journal(entries: list[dict], title: str = 'Журнал исправлений') -> None:
    """Журнал правок за запуск. Пустой — короткое сообщение (R09: без KeyError)."""
    if not entries:
        info('Исправлений не вносилось.')
        return
    if not HAS_RICH:
        print(f'=== {title} ({len(entries)}) ===')
        for e in entries:
            if not isinstance(e, dict):
                continue
            rnd = ' (часть времени случайна)' if e.get('randomized') else ''
            print(f"{e.get('ts', '?')} {e.get('name', '?')} {e.get('date', '?')}: "
                  f"{e.get('action', '?')}: {e.get('before', '?')} -> {e.get('after', '?')}{rnd}")
        return
    from rich.markup import escape

    console = get_console()
    table = Table(title=f'{title} ({len(entries)})')
    table.add_column('Время')
    table.add_column('Сотрудник')
    table.add_column('Дата')
    table.add_column('Действие')
    table.add_column('Было -> стало')
    for e in entries:
        if not isinstance(e, dict):
            continue
        rnd = ' [yellow](случайное время)[/yellow]' if e.get('randomized') else ''
        # Значения содержат «[work]», «[sick]»: без escape rich съедает их как теги.
        table.add_row(escape(str(e.get('ts', '?'))), escape(str(e.get('name', '?'))),
                      escape(str(e.get('date', '?'))), escape(str(e.get('action', '?'))),
                      f"{escape(str(e.get('before', '?')))} -> "
                      f"{escape(str(e.get('after', '?')))}{rnd}")
    console.print(table)


def print_salary_report(rows: list[dict], title: str = 'Итоги месяца') -> None:
    """Финальный отчет: дни + деньги одной таблицей.

    Строки — из build_preview_rows (там уже salary/milk/total).
    Деньги — format_money, длительности — str_timedelta: как в Excel/HTML.
    """
    from core.money import format_money

    if not rows:
        warn('Нет данных расчета для отчета.')
        return
    if not HAS_RICH:
        print(f'=== {title} ===')
        for r in rows:
            print(f"{r['name']}: будни={r['work']} (+{r['overtime']}/-{r['undertime']}) "
                  f"вых={r['weekend']} отп={r['vacation']} "
                  f"оклад={format_money(r['salary'])} молоко={format_money(r['milk'])} "
                  f"итого={format_money(r['total'])}")
        return
    console = get_console()
    table = Table(title=title, show_lines=True)
    table.add_column('Сотрудник')
    table.add_column('Будни', justify='right')
    table.add_column('+ / -', justify='right')
    table.add_column('Вых', justify='right')
    table.add_column('Отп', justify='right')
    table.add_column('Оклад', justify='right')
    table.add_column('Молоко', justify='right')
    table.add_column('Итого', justify='right', style='bold green')
    for r in rows:
        table.add_row(
            r['name'],
            str(r['work']),
            f"+{r['overtime']} / -{r['undertime']}",
            str(r['weekend']),
            str(r['vacation']),
            format_money(r['salary']),
            format_money(r['milk']),
            format_money(r['total']),
        )
    console.print(table)
