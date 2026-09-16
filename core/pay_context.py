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
                    f'на {ctx.month_start} — учёт по DAT, начисление по SQLite'
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
        # 2. SQLite-сотрудники вне DAT-справочника.
        dat_ids = set((dat_staff or {}).keys())
        for emp_id in sorted(set(sqlite_emps) - dat_ids):
            warnings.append(
                f'ID {emp_id}: есть только в SQLite — отметки DAT будут отброшены '
                f'при импорте (требуется объединённый справочник)'
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
