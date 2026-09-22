"""Аргументы запуска и интерактивный выбор режима расчёта."""

import argparse
import getpass
import sys
from decimal import Decimal


KEY_REQUIREMENTS = 'нужны только цифры 0–9, длина 3–122'


def parse_secret_key(key_input: str) -> tuple[Decimal, bool, str | None]:
    """Вернуть (ключ, режим зарплаты, диагностика без значения ключа).

    Диапазон длины ключа (3-122) сам по себе не гарантирует, что ключ×ставка
    квантуется в Decimal(28) — при переполнении load_wage_rates даёт
    ConfigError с файлом и строкой, а не роняет расчёт InvalidOperation.
    """
    if key_input in ('t', '0'):
        return Decimal('0.00'), False, None
    if key_input.isascii() and key_input.isdecimal() and 3 <= len(key_input) <= 122:
        # Строковое преобразование не зависит от точности Decimal-контекста:
        # деление длинного ключа на 100 округляло значащие цифры после 28-й.
        return Decimal(f'{key_input[:-2]}.{key_input[-2:]}'), True, None
    return Decimal('0.00'), False, (
        f'ключ не распознан ({KEY_REQUIREMENTS}, или t для режима без зарплаты)'
    )


def _ask_key_hidden() -> Decimal | None:
    """Три попытки скрытого ввода; пустой ввод возвращает в меню."""
    for attempt in range(1, 4):
        try:
            raw = getpass.getpass('Секретный ключ (скрытый ввод, пусто — назад): ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(130)
        if not raw:
            return None
        secret, salary_mode, _ = parse_secret_key(raw)
        if salary_mode:
            return secret
        print(f'ВНИМАНИЕ: {KEY_REQUIREMENTS} (попытка {attempt}/3).')
    print('Ключ не принят трижды — завершение с кодом 1, чтобы не посчитать нули молча.')
    sys.exit(1)


def resolve_secret_key(args: argparse.Namespace) -> tuple[Decimal, bool]:
    """Явный -k, меню в терминале или учёт без зарплаты при запуске через pipe."""
    if args.key is not None:
        secret, salary_mode, warning = parse_secret_key(args.key)
        if warning:
            print(f'ВНИМАНИЕ: {warning}. Расчет в режиме БЕЗ зарплаты: оклад будет нулевым.')
        return secret, salary_mode
    if not sys.stdin.isatty():
        print('Ключ -k не передан (неинтерактивный запуск): режим БЕЗ зарплаты.')
        return Decimal('0.00'), False
    from core import ui

    try:
        while True:
            ui.info('Запуск без ключа. Выберите режим: '
                    '[1] учёт времени без зарплаты  '
                    '[2] расчёт зарплаты (ключ — скрытым вводом)  [0] выход')
            choice = ui.ask_menu('Режим:', ('1', '2'))
            if choice in ('0', 'q', 'отмена'):
                print('Выход.')
                sys.exit(0)
            if choice == '1':
                return Decimal('0.00'), False
            secret = _ask_key_hidden()
            if secret is not None:
                return secret, True
    except KeyboardInterrupt:
        print('\nПрервано пользователем.')
        sys.exit(130)
    except EOFError:
        print('\nВвод недоступен: режим БЕЗ зарплаты.')
        return Decimal('0.00'), False


def _year(value: str) -> int:
    try:
        year = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('год должен быть целым числом от 1900 до 2100') from None
    if not 1900 <= year <= 2100:
        raise argparse.ArgumentTypeError('год должен быть от 1900 до 2100')
    return year


def _month(value: str) -> int:
    try:
        month = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('месяц должен быть целым числом от 1 до 12') from None
    if not 1 <= month <= 12:
        raise argparse.ArgumentTypeError('месяц должен быть от 1 до 12')
    return month


def validate_period(year: int | None, month: int | None) -> tuple[int, int]:
    """Проверить год/месяц с понятной диагностикой (F19).

    Возвращает (year, month). Ошибка — ValueError с текстом для вызывающего
    кода (напр. периода, восстановленного из сессии, а не только ввода).
    """
    if year is None or month is None:
        raise ValueError('нужны год и месяц (например, -y 2026 -m 7)')
    if not 1900 <= year <= 2100:
        raise ValueError(f'год {year} вне поддерживаемого 1900..2100')
    if not 1 <= month <= 12:
        raise ValueError(f'месяц {month} вне 1..12')
    return year, month


def resolve_period(args: argparse.Namespace, parser: argparse.ArgumentParser) -> tuple[int, int]:
    """Проверить аргументы и недостающие значения, введённые через input."""
    try:
        year = args.year if args.year is not None else _year(input('Введите год: '))
        month = args.month if args.month is not None else _month(input('Введите месяц: '))
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    except EOFError:
        parser.error('ввод недоступен: укажите период через -y и -m')
    except KeyboardInterrupt:
        print('\nПрервано пользователем.')
        sys.exit(130)
    return year, month


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Система расчета заработной платы и учета рабочего времени'
    )
    parser.add_argument('-f', '--file', default='1_attlog.dat', help='Файл данных')
    parser.add_argument('-y', '--year', type=_year, help='Год (1900–2100)')
    parser.add_argument('-m', '--month', type=_month, help='Месяц (1–12)')
    parser.add_argument('-k', '--key', default=None,
                        help='Секретный ключ (или t для без зарплаты). '
                             'Без -k: меню в терминале (скрытый ввод), '
                             'вне терминала — режим без зарплаты')
    parser.add_argument('--no-edit', action='store_true', help='Пропустить интерактивное редактирование')
    parser.add_argument('--resume', action='store_true',
                        help='Восстановить сохраненную сессию из temporary.json '
                             '(журнал правок восстанавливается; старый '
                             'temporary.pickle не поддерживается)')
    parser.add_argument('--include-empty', action='store_true',
                        help='Включить в расчет сотрудников без единой отметки за месяц '
                             '(действующий, но отсутствовал весь месяц: отпуск/прогул)')
    parser.add_argument('--pay-dir', default=None,
                        help='SQLite-справочник новой модели оплаты '
                             '(дефолт: <data-dir>/pay_directory.db; '
                             'нет файла/условий на месяц — legacy-режим)')
    parser.add_argument('--data-dir', default='data', help='Каталог входных данных (DAT + справочники)')
    parser.add_argument('--output-dir', default='result',
                        help='Каталог результатов (Excel, HTML, версии, сессия)')
    return parser
