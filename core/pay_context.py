"""Единый контекст расчёта (Этап 3, F01/F02/F05).

Контекст периода выбирается один раз на запуск, до анализа и правок:
период, режим оплаты (salary_mode из -k), режим модели (new/legacy),
источник справочников и действующие условия. Отчёты отображают уже
определённый состав, а не фильтруют его повторно по DAT-глобалам.

Пока контекст — лёгкая оболочка над resolve_pay_mode + диагностика
расхождений DAT/SQLite. Полный переход всех этапов на явный контекст
(импорт, анализ, дневной учёт) — следующими шагами; здесь фиксируем
режим до правок и делаем расхождения явными вместо молчаливых.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PayrollContext:
    year: int
    month: int
    month_start: str
    salary_mode: bool
    mode: str  # 'new' | 'legacy'
    db_path: str
    settings: Any | None = None
    warnings: list[str] = field(default_factory=list)
    # R02/P3-B: неизменный снимок расчёта — штат, правила, календарь, участники.
    staff: dict | None = None
    rules_by_role: dict | None = None
    workdays_D: int | None = None
    calendar_dates: dict | None = None
    db_meta: dict | None = None


def resolve_context(db_path: str, year: int, month: int,
                    salary_mode: bool = True) -> PayrollContext:
    """Определить режим периода до правок. Ошибки БД — PayrollError (фатально)."""
    from core.payroll import new_regime_available

    month_start = f'{year:04d}-{month:02d}-01'
    settings = new_regime_available(db_path, year, month)
    mode = 'new' if settings is not None else 'legacy'
    return PayrollContext(
        year=year, month=month, month_start=month_start,
        salary_mode=bool(salary_mode), mode=mode,
        db_path=db_path, settings=settings,
    )


def diagnose_roster_divergence(ctx: PayrollContext, dat_staff: dict,
                               data_array: dict | None = None) -> list[str]:
    """Сравнить DAT-справочник с SQLite-ростером на month_start (только new-режим).

    Возвращает предупреждения для консоли/журнала. Не пишет в БД.
    Молчаливые расхождения F02 становятся явными до начислений.
    """
    if ctx.mode != 'new':
        return []
    import sqlite3 as _sqlite3

    from core.payroll import PayrollError
    from core.pay_store import connect, get_assignment, get_role_rule, list_exceptions

    warnings: list[str] = []
    try:
        con = connect(ctx.db_path)
    except _sqlite3.Error as e:
        raise PayrollError(f'{ctx.db_path}: не удалось открыть справочник ({e}).') from e
    try:
        try:
            sqlite_emps = {r['id']: r for r in con.execute('SELECT * FROM employees')}
            sqlite_exceptions = set(list_exceptions(con).keys())
        except _sqlite3.Error as e:
            raise PayrollError(f'{ctx.db_path}: ошибка чтения ростера ({e}).') from e
        # 1. DAT-роль vs SQLite-назначение.
        for emp_id, emp in (dat_staff or {}).items():
            dat_role = getattr(emp, 'role_id', None)
            try:
                assigned = get_assignment(con, emp_id, ctx.month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{ctx.db_path}: ошибка чтения назначений ({e}).') from e
            if assigned is None:
                warnings.append(
                    f'ID {emp_id}: нет назначения SQLite на {ctx.month_start} '
                    f'(DAT-роль {dat_role}) — новая модель прервётся с ошибкой'
                )
                continue
            sqlite_role, _to = assigned
            if dat_role is not None and int(dat_role) != int(sqlite_role):
                warnings.append(
                    f'ID {emp_id}: роль DAT={dat_role} vs SQLite={sqlite_role} '
                    f'на {ctx.month_start} — используется SQLite (new-режим)'
                )
            try:
                rule = get_role_rule(con, int(sqlite_role), ctx.month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{ctx.db_path}: ошибка чтения правил ({e}).') from e
            if rule is not None and not rule.participates:
                warnings.append(
                    f'ID {emp_id}: SQLite-правило роли {sqlite_role} не участвует '
                    f'({rule.exclude_reason or "без причины"}) — из начислений исключён'
                )
        # 2. SQLite-сотрудники вне DAT-справочника (R01: импорт объединённый).
        dat_ids = set((dat_staff or {}).keys())
        for emp_id in sorted(set(sqlite_emps) - dat_ids):
            warnings.append(
                f'ID {emp_id}: есть только в SQLite — включён через объединённый штат'
            )
        # 3. Персональные исключения SQLite.
        for emp_id in sorted(sqlite_exceptions):
            if emp_id in dat_ids:
                warnings.append(
                    f'ID {emp_id}: персональное исключение SQLite — '
                    f'в bundle.results его не будет, только дашборд'
                )
        # 4. Отметки неизвестных ID уже в таблице (прошли фильтр) — явная диагностика.
        if data_array:
            known = dat_ids | set(sqlite_emps)
            unknown = sorted({e for day in data_array.values() for e in day} - known)
            for emp_id in unknown:
                warnings.append(f'ID {emp_id}: отметки без карточки DAT/SQLite — отброшены')
    finally:
        try:
            con.close()
        except Exception:
            pass
    return warnings


def combined_staff_for_import(dat_staff: dict, db_path: str,
                               month_start: str) -> dict:
    """Объединённый штат для импорта и состава в new-режиме (F02-union).

    DAT-копия + SQLite-сотрудники вне DAT как EmployeeData. Для пересекающихся
    ID роль берётся из SQLite-назначения на month_start (SQLite — источник
    новой модели), имя — из SQLite-карточки. Без назначения — роль 1-заглушка
    для сохранения отметок; отсутствие назначения затем фатально до правок.
    Не пишет в БД; ошибки чтения — PayrollError.
    """
    import sqlite3 as _sqlite3

    from pathlib import Path as _Path

    from core.config import EmployeeData as _EmployeeData
    from core.payroll import PayrollError

    combined = dict(dat_staff or {})
    if not _Path(db_path).exists():
        return combined
    from core.pay_store import connect, get_assignment

    try:
        con = connect(db_path)
    except _sqlite3.Error as e:
        raise PayrollError(f'{db_path}: не удалось открыть справочник ({e}).') from e
    try:
        try:
            sqlite_emps = {r['id']: r for r in con.execute('SELECT * FROM employees')}
            role_names = {r['id']: r['name'] for r in con.execute('SELECT id, name FROM roles')}
        except _sqlite3.Error as e:
            raise PayrollError(f'{db_path}: ошибка чтения ростера ({e}).') from e
        for emp_id, row in sqlite_emps.items():
            try:
                assigned = get_assignment(con, emp_id, month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения назначений ({e}).') from e
            if emp_id in combined:
                # R13: SQLite — авторитет ФИО и роли в new-режиме независимо
                # от смены роли. Пустые SQLite-ИО — fallback к DAT.
                cur = combined[emp_id]
                sqlite_role = int(assigned[0]) if assigned is not None else None
                want_first = (row['first_name'] or '').strip() or getattr(cur, 'first_name', '')
                want_last = (row['last_name'] or '').strip() or getattr(cur, 'last_name', '')
                want_role = sqlite_role if sqlite_role is not None else getattr(cur, 'role_id', None)
                want_role_name = (role_names.get(want_role, '')
                                  if want_role is not None else getattr(cur, 'role_name', ''))
                cur_first = getattr(cur, 'first_name', '')
                cur_last = getattr(cur, 'last_name', '')
                cur_role = getattr(cur, 'role_id', None)
                cur_role_name = getattr(cur, 'role_name', '')
                if (cur_first, cur_last, cur_role, cur_role_name) != (
                        want_first, want_last, want_role, want_role_name):
                    combined[emp_id] = _EmployeeData(
                        id=int(emp_id),
                        first_name=want_first,
                        last_name=want_last,
                        role_id=want_role,
                        role_name=want_role_name,
                    )
                continue
            if assigned is not None:
                role_id = int(assigned[0])
            else:
                role_id = 1
            combined[int(emp_id)] = _EmployeeData(
                id=int(emp_id),
                first_name=row['first_name'] or '',
                last_name=row['last_name'] or '',
                role_id=role_id,
                role_name=role_names.get(role_id, ''),
            )
        return combined
    finally:
        try:
            con.close()
        except Exception:
            pass


def load_rules_map(db_path: str, month_start: str, staff: dict) -> dict:
    """Действующие SQLite-правила участников на 1-е число (R02).

    Возвращает {role_id: RoleRule}. Отсутствие версии для роли участника —
    PayrollError до анализа/правок (не KeyError в середине дневных строк).
    Не пишет в БД.
    """
    import sqlite3 as _sqlite3

    from pathlib import Path as _Path

    from core.payroll import PayrollError

    if not _Path(db_path).exists():
        raise PayrollError(f'{db_path}: справочник не найден для загрузки правил.')
    from core.pay_store import connect, get_assignment, get_role_rule

    try:
        con = connect(db_path)
    except _sqlite3.Error as e:
        raise PayrollError(f'{db_path}: не удалось открыть справочник ({e}).') from e
    try:
        needed: set[int] = set()
        for emp_id, emp in (staff or {}).items():
            try:
                assigned = get_assignment(con, int(emp_id), month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения назначений ({e}).') from e
            if assigned is None:
                continue
            needed.add(int(assigned[0]))
        # Также роли из карточек (для ранней диагностики неизвестных ролей).
        for emp in (staff or {}).values():
            rid = getattr(emp, 'role_id', None)
            if rid is not None:
                try:
                    needed.add(int(rid))
                except (ValueError, TypeError):
                    pass
        rules: dict = {}
        for role_id in sorted(needed):
            try:
                rule = get_role_rule(con, int(role_id), month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения правил ({e}).') from e
            if rule is None:
                raise PayrollError(
                    f'роль {role_id}: нет версии правил на {month_start} — '
                    f'заведите версию до анализа')
            rules[int(role_id)] = rule
        return rules
    finally:
        try:
            con.close()
        except Exception:
            pass


def sqlite_excluded_map(db_path: str, month_start: str) -> dict[int, str]:
    """{emp_id: причина} исключений новой модели: participates=False + exceptions.

    Для дашборда/отчётов при bundle, чтобы состав совпадал везде (F02).
    Ошибки чтения — PayrollError. Пустой dict при отсутствии БД — legacy.
    """
    import sqlite3 as _sqlite3

    from pathlib import Path as _Path

    from core.payroll import PayrollError

    if not _Path(db_path).exists():
        return {}
    from core.pay_store import connect, get_role_rule, list_exceptions

    try:
        con = connect(db_path)
    except _sqlite3.Error as e:
        raise PayrollError(f'{db_path}: не удалось открыть справочник ({e}).') from e
    try:
        try:
            rows = list(con.execute('SELECT id FROM employees'))
            emp_ids = [r['id'] for r in rows]
            exceptions = list_exceptions(con)
        except _sqlite3.Error as e:
            raise PayrollError(f'{db_path}: ошибка чтения ростера ({e}).') from e
        out: dict[int, str] = {}
        for emp_id, reason in exceptions.items():
            out[int(emp_id)] = reason or 'персональное исключение SQLite'
        # participates=False через назначение на month_start.
        from core.pay_store import get_assignment

        for emp_id in emp_ids:
            if emp_id in out:
                continue
            try:
                assigned = get_assignment(con, emp_id, month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения назначений ({e}).') from e
            if assigned is None:
                continue
            role_id, _to = assigned
            try:
                rule = get_role_rule(con, int(role_id), month_start)
            except _sqlite3.Error as e:
                raise PayrollError(f'{db_path}: ошибка чтения правил ({e}).') from e
            if rule is not None and not rule.participates:
                out[int(emp_id)] = rule.exclude_reason or f'роль {role_id} не участвует'
        return out
    finally:
        try:
            con.close()
        except Exception:
            pass
