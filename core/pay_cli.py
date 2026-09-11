"""Консольное управление справочниками оплаты (план roles_rates, §4.1).

Первый интерфейс раздела «Справочники»: команды init/migrate/template/export/
import/show/rules-history. Редактирование через CLI и импорт используют одни
сервисы и проверки (pay_store/pay_toml).
"""

from __future__ import annotations

import argparse
import sys

from core.pay_store import (
    DEFAULT_DB_PATH, DEFAULT_TRANSITION, connect, get_pay_settings, get_role_rule,
    get_seniority_scale, init_db, list_exceptions, migrate_from_dat,
    role_rule_history, seed_defaults,
)
from core.pay_toml import export_toml, generate_template, import_toml


def _db_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument('--db', default=DEFAULT_DB_PATH, help='Файл SQLite-справочника')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Справочники оплаты (общая база 60 000 руб.)')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('init', help='Создать БД и внести стартовые условия')
    _db_arg(p)

    p = sub.add_parser('migrate', help='Перенести сотрудников/роли/исключения из .dat')
    _db_arg(p)
    p.add_argument('--dat-dir', default='data/variable_data_for_app')
    p.add_argument('--from', dest='from_date', default=DEFAULT_TRANSITION)

    p = sub.add_parser('template', help='Печать пустого TOML-шаблона')
    p.add_argument('--out', default=None, help='Файл (по умолчанию — stdout)')

    p = sub.add_parser('export', help='Экспорт справочника в TOML')
    _db_arg(p)
    p.add_argument('--section', default=None)
    p.add_argument('--out', default=None)

    p = sub.add_parser('import', help='Импорт TOML (с предпросмотром)')
    _db_arg(p)
    p.add_argument('file')
    p.add_argument('--dry-run', action='store_true', help='Только предпросмотр')

    p = sub.add_parser('show', help='Действующие условия на дату')
    _db_arg(p)
    p.add_argument('--date', default='2026-09-01')

    p = sub.add_parser('rules-history', help='История версий правил роли')
    _db_arg(p)
    p.add_argument('role_id', type=int)
    return parser


def _print_report(report: dict) -> int:
    print(f"Добавлений: {len(report['added'])}, "
          f"без изменений: {len(report['unchanged'])}, ошибок: {len(report['errors'])}")
    for section, key in report['added']:
        print(f'  + {section}[{key}]')
    for err in report['errors']:
        print(f'  ! {err}')
    return 1 if report['errors'] else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == 'init':
        init_db(args.db)
        con = connect(args.db)
        try:
            seed_defaults(con)
        finally:
            con.close()
        print(f'Справочник {args.db}: схема создана, стартовые условия внесены.')
        return 0
    if args.cmd == 'migrate':
        con = init_db(args.db)
        try:
            report = migrate_from_dat(con, args.dat_dir, args.from_date)
        finally:
            con.close()
        print(f"Ролей: {report['roles']}, сотрудников: {report['employees']}, "
              f"исключений: {report['exceptions']}, пропущено: {report['skipped']}")
        return 0
    if args.cmd == 'template':
        text = generate_template()
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f'Шаблон записан: {args.out}')
        else:
            print(text, end='')
        return 0
    if args.cmd == 'export':
        text = export_toml(args.db, args.section)
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f'Экспортировано: {args.out}')
        else:
            print(text, end='')
        return 0
    if args.cmd == 'import':
        with open(args.file, encoding='utf-8') as f:
            text = f.read()
        report = import_toml(args.db, text, dry_run=args.dry_run)
        if args.dry_run:
            print('Предпросмотр (запись не выполнялась):')
        return _print_report(report)
    if args.cmd == 'show':
        con = connect(args.db)
        try:
            settings = get_pay_settings(con, args.date)
            if settings is None:
                print(f'На {args.date}: общие условия не заданы.')
                return 1
            print(f'На {args.date}: база {settings.monthly_base} руб., '
                  f'H_base {settings.base_day_hours} ч, '
                  f'бонус полного месяца {settings.full_month_bonus} руб. '
                  f'(с {settings.effective_from}).')
            for (rid,) in con.execute('SELECT id FROM roles ORDER BY id'):
                rule = get_role_rule(con, rid, args.date)
                name = con.execute('SELECT name FROM roles WHERE id=?', (rid,)).fetchone()['name']
                if rule is None:
                    print(f'  роль {rid} {name}: правило на дату не задано')
                    continue
                bonuses = ''.join((
                    'П' if rule.overtime_eligible else '-',
                    'М' if rule.full_month_eligible else '-',
                    'С' if rule.seniority_eligible else '-',
                ))
                part = 'участвует' if rule.participates else f'исключена ({rule.exclude_reason})'
                print(f'  роль {rid} {name}: {rule.time_mode}, норма {rule.shift_norm_hours} ч, '
                      f'{part}, бонусы П/М/С: {bonuses}.')
            print(f'  Стажевая шкала: {get_seniority_scale(con, args.date)}')
            exc = list_exceptions(con)
            print(f'  Персональные исключения ({len(exc)}): '
                  + (', '.join(f'{k} ({v})' for k, v in exc.items()) or '—'))
            n_assign = con.execute('SELECT COUNT(*) c FROM assignments').fetchone()['c']
            print(f'  Назначений всего: {n_assign}.')
        finally:
            con.close()
        return 0
    if args.cmd == 'rules-history':
        con = connect(args.db)
        try:
            for rule in role_rule_history(con, args.role_id):
                print(f'{rule.role_id}: {rule.time_mode}, норма {rule.shift_norm_hours}, '
                      f'участие={int(rule.participates)}, бонусы='
                      f"{int(rule.overtime_eligible)}{int(rule.full_month_eligible)}"
                      f"{int(rule.seniority_eligible)}")
        finally:
            con.close()
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
