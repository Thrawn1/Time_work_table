"""Строгий разбор ручного ввода времени.

Правила:
- Формат: "Ч [М [С]]", от 1 до 3 чисел через пробел. Примеры: "8", "8 30", "8 30 00".
- Каждый токен: только цифры, длина 1-2 символа. "008", "ab", "8.5" — ошибка.
- Диапазоны: часы 0-23, минуты/секунды 0-59. "08 99 00" — ошибка, а не рандом.
- Лишние токены ("08 30 00 extra") — ошибка целиком, а не отбрасывание.
- Случайная подстановка — ТОЛЬКО для пропущенных компонентов ("8" -> минуты/секунды
  случайно). Явная опечатка никогда не заменяется рандомом.
- Функции не вызывают input() — повторный запрос делает вызывающий диалог.
"""

import random

CANCEL_TOKENS = {'0', 'q', 'й', 'отмена', 'cancel', 'exit'}


def minutes_or_seconds_random():
    '''Функция возращает случайное значение минут или секунд  в диапазоне от 0 до 59'''
    return random.randint(0, 59)


def parse_time_input(time_value: str) -> tuple[dict, list, str | None]:
    """Строго разобрать строку времени.

    Возвращает (data_time, missing, error):
    - data_time: {'H': int|None, 'M': int|None, 'S': int|None} — явные значения.
    - missing: ключи, которых нет во вводе (кандидаты на рандом, только M/S).
    - error: текст ошибки или None если явные токены корректны.

    Пустой ввод, лишние токены, нецифровые значения, длина >2 и выход за
    диапазон — это error, а не missing.
    """
    data_time: dict = {'H': None, 'M': None, 'S': None}
    if time_value is None:
        return data_time, [], 'Пустой ввод: введите время в формате "Ч М С".'
    stripped = time_value.strip()
    if not stripped:
        return data_time, [], 'Пустой ввод: введите время в формате "Ч М С".'
    if stripped.lower() in CANCEL_TOKENS:
        return data_time, [], '__CANCEL__'
    tokens = stripped.split()
    if len(tokens) > 3:
        return (
            data_time,
            [],
            f'Лишние данные: ожидалось до 3 чисел "Ч М С", получено {len(tokens)}. '
            'Введите заново.',
        )
    keys = ['H', 'M', 'S']
    for i, tok in enumerate(tokens):
        key = keys[i]
        if not tok.isdigit():
            return data_time, [], f'Некорректное значение "{tok}": нужны только цифры.'
        if len(tok) > 2:
            return (
                data_time,
                [],
                f'Некорректное значение "{tok}": должно быть 1-2 цифры (например "8", а не "008").',
            )
        value = int(tok)
        if key == 'H':
            if value > 23:
                return data_time, [], f'Часы "{tok}": должно быть 0-23.'
            data_time['H'] = value
        else:
            if value > 59:
                label = 'Минуты' if key == 'M' else 'Секунды'
                return data_time, [], f'{label} "{tok}": должно быть 0-59.'
            data_time[key] = value
    missing = [k for k, v in data_time.items() if v is None]
    return data_time, missing, None


def fill_missing_with_random(data_time: dict, missing: list) -> tuple[dict, list]:
    """Дозаполнить пропущенные M/S случайными значениями.

    H никогда не дозаполняется — его отсутствие означает ошибку ввода выше.
    Возвращает (filled_dict, randomized_keys).
    """
    filled = dict(data_time)
    randomized: list = []
    for key in missing:
        if key in ('M', 'S'):
            filled[key] = minutes_or_seconds_random()
            randomized.append(key)
        # H в missing сюда попадать не должен: пустой ввод уже отклонен как error.
    return filled, randomized


def format_time(data_time: dict) -> str:
    """Словарь {'H','M','S'} -> строка 'HH MM SS'."""
    try:
        h, m, s = int(data_time['H']), int(data_time['M']), int(data_time['S'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Неполное время: часы, минуты и секунды должны быть заданы.')
    if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
        raise ValueError('Время вне диапазона: Ч 0-23, М/С 0-59.')
    return f'{h:02d} {m:02d} {s:02d}'


def parse_and_fill(time_value: str) -> tuple[str, list]:
    """Разобрать ввод и вернуть (time_str 'HH MM SS', randomized_keys).

    Raises ValueError с текстом для пользователя при любой ошибке,
    '__CANCEL__' транслируется в ValueError('__CANCEL__') — вызывающий диалог
    превращает его в пропуск дня.
    """
    data_time, missing, error = parse_time_input(time_value)
    if error is not None:
        raise ValueError(error)
    filled, randomized = fill_missing_with_random(data_time, missing)
    return format_time(filled), randomized


def analize_input_time(time_value: str):
    """Совместимость: строгий разбор в старом формате (значения — строки)."""
    data_time, missing, error = parse_time_input(time_value)
    if error is not None and error != '__CANCEL__':
        # Старый контракт возвращал (dict, error_keys); ошибку кодируем так:
        # все явные значения сбрасываются, в error — ключи с проблемами.
        # Точный текст ошибки доступен через parse_time_input / parse_and_fill.
        str_data = {'H': None, 'M': None, 'S': None}
        for k, v in data_time.items():
            str_data[k] = str(v) if v is not None else None
        err_keys = list(missing)
        # Помечаем первый токен как проблемный, чтобы старый вызывающий код
        # не считал ввод валидным. Детали — в тексте error.
        if not err_keys:
            err_keys = ['H']
        return (str_data, err_keys)
    str_data = {k: (str(v) if v is not None else None) for k, v in data_time.items()}
    return (str_data, list(missing))


def updating_missing_values(data_time: dict, error_time_value: list):
    """Совместимость: дозаполняет M/S рандомом, H с ошибкой — ValueError.

    Больше НЕ вызывает input() — повторный запрос делает вызывающий диалог.
    """
    if 'H' in error_time_value and data_time.get('H') is None:
        raise ValueError('Часы нужно ввести заново полностью (0-23, 1-2 цифры).')
    for miss_key in error_time_value:
        if miss_key in ('M', 'S'):
            data_time[miss_key] = minutes_or_seconds_random()
    return data_time


def get_str_time(data_time: dict):
    """Функция принимает словарь с временем и возвращает строку с временем"""
    H = str(data_time['H'])
    M = str(data_time['M'])
    S = str(data_time['S'])
    if len(H) == 1:
        H = '0' + H
    if len(M) == 1:
        M = '0' + M
    if len(S) == 1:
        S = '0' + S
    str_time = H + ' ' + M + ' ' + S
    return str_time


def time_data_generation(time_value: str):
    """Строгая генерация: вернет 'HH MM SS' или бросит ValueError.

    Случайно дозаполняются ТОЛЬКО пропущенные M/S. Опечатки — ValueError.
    """
    time_str, _randomized = parse_and_fill(time_value)
    return time_str
