from os import path
from contextlib import contextmanager
import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from core.money import quantize_rate, as_decimal

DATA_DIR = 'data'
VARIABLE_DATA_DIR = path.join(DATA_DIR, 'variable_data_for_app')

ID_EMPLOYEE_FILE = path.join(VARIABLE_DATA_DIR, 'id_employee.dat')
ROLES_FILE = path.join(VARIABLE_DATA_DIR, 'roles_employee.dat')
WAGE_RATES_FILE = path.join(VARIABLE_DATA_DIR, 'wage_rates.dat')
HOLIDAYS_FILE = path.join(VARIABLE_DATA_DIR, 'holidays.dat')
POSTPONED_DAYS_FILE = path.join(VARIABLE_DATA_DIR, 'postponed_working_days.dat')
SETTLEMENT_EXCEPTIONS_FILE = path.join(VARIABLE_DATA_DIR, 'settlement_exceptions.dat')

#: Устаревший файл ключа (Этап 7, F18): больше не создаётся и не читается.
#: Оставлен здесь для очистки и диагностики старых установок.
LEGACY_SECRET_FILE = '_secret_key.tmp'


class ConfigError(RuntimeError):
    """Ошибка текстового справочника с именем файла, строкой и полем (F19)."""


def set_data_dir(dir_path: str) -> None:
    """Переключить каталог входных данных (CLI: --data-dir).

    Вызывать до load_config() и любых чтений: пути справочников
    пересчитываются от нового корня. Дефолт 'data' сохраняет
    прежнее поведение и совместимость с тестами.
    """
    global DATA_DIR, VARIABLE_DATA_DIR
    global ID_EMPLOYEE_FILE, ROLES_FILE, WAGE_RATES_FILE
    global HOLIDAYS_FILE, POSTPONED_DAYS_FILE, SETTLEMENT_EXCEPTIONS_FILE
    DATA_DIR = dir_path
    VARIABLE_DATA_DIR = path.join(dir_path, 'variable_data_for_app')
    ID_EMPLOYEE_FILE = path.join(VARIABLE_DATA_DIR, 'id_employee.dat')
    ROLES_FILE = path.join(VARIABLE_DATA_DIR, 'roles_employee.dat')
    WAGE_RATES_FILE = path.join(VARIABLE_DATA_DIR, 'wage_rates.dat')
    HOLIDAYS_FILE = path.join(VARIABLE_DATA_DIR, 'holidays.dat')
    POSTPONED_DAYS_FILE = path.join(VARIABLE_DATA_DIR, 'postponed_working_days.dat')
    SETTLEMENT_EXCEPTIONS_FILE = path.join(VARIABLE_DATA_DIR, 'settlement_exceptions.dat')


@dataclass
class Role:
    id: int
    name: str


@dataclass
class EmployeeData:
    id: int
    first_name: str
    last_name: str
    role_id: int
    role_name: str


ROLES: dict[int, Role] = {}
EMPLOYEES: dict[int, EmployeeData] = {}
SETTLEMENT_EXCEPTIONS: list[int] = []

#: Исключения, выбранные оператором на текущем запуске: {id: причина}. В файлы
#: справочников не пишутся; живут в сессии (--resume) и в пакете расчёта.
#: Изменяется только на месте (потребители держат ссылку на этот объект).
MANUAL_EXCLUSIONS: dict[int, str] = {}
MANUAL_EXCLUSION_REASON = 'исключён вручную'


@contextmanager
def preserve_config():
    """Изолировать запуск, сохранив пути, справочники и ключ для их потребителей."""
    global _SECRET_KEY
    path_keys = (
        'DATA_DIR', 'VARIABLE_DATA_DIR', 'ID_EMPLOYEE_FILE', 'ROLES_FILE',
        'WAGE_RATES_FILE', 'HOLIDAYS_FILE', 'POSTPONED_DAYS_FILE',
        'SETTLEMENT_EXCEPTIONS_FILE',
    )
    saved_paths = {key: globals()[key] for key in path_keys}
    saved_roles, saved_employees = ROLES.copy(), EMPLOYEES.copy()
    saved_exceptions = SETTLEMENT_EXCEPTIONS.copy()
    saved_manual = MANUAL_EXCLUSIONS.copy()
    saved_secret_key = _SECRET_KEY
    from core.file_parser import clear_calendar_cache

    clear_calendar_cache()
    try:
        yield
    finally:
        globals().update(saved_paths)
        ROLES.clear()
        ROLES.update(saved_roles)
        EMPLOYEES.clear()
        EMPLOYEES.update(saved_employees)
        SETTLEMENT_EXCEPTIONS[:] = saved_exceptions
        MANUAL_EXCLUSIONS.clear()
        MANUAL_EXCLUSIONS.update(saved_manual)
        _SECRET_KEY = saved_secret_key
        clear_calendar_cache()


def load_config() -> None:
    """Загрузить справочники с предметной диагностикой до начала расчёта (F19/R18).

    R18: дубли ID, ссылки на неизвестные роли и диапазоны ставок проверяются
    с номером строки; готовая конфигурация применяется целиком после успешной
    проверки. Ошибки формата/доступа — ConfigError с файлом, строкой и полем.
    """
    try:
        roles = _load_roles()
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f'{ROLES_FILE}: не удалось прочитать справочник ролей: {e}') from e
    try:
        employees = _load_employees(roles)
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f'{ID_EMPLOYEE_FILE}: не удалось прочитать справочник сотрудников: {e}') from e
    try:
        exceptions = _load_settlement_exceptions()
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(
            f'{SETTLEMENT_EXCEPTIONS_FILE}: не удалось прочитать исключения: {e}') from e
    # R18: неизвестная DAT-роль — диагностика до анализа, а не KeyError в расчёте.
    for emp_id, emp in employees.items():
        if emp.role_id not in roles:
            raise ConfigError(
                f'{ID_EMPLOYEE_FILE}: сотрудник {emp_id} ссылается на неизвестную '
                f'роль {emp.role_id} (нет в {ROLES_FILE})')
    ROLES.clear()
    ROLES.update(roles)
    EMPLOYEES.clear()
    EMPLOYEES.update(employees)
    SETTLEMENT_EXCEPTIONS.clear()
    SETTLEMENT_EXCEPTIONS.extend(exceptions)


def _parse_roles_line(line: str, lineno: int, source: str) -> tuple[int, str]:
    """Разобрать строку '[id] название' (пробелы/табуляция вокруг — любые)."""
    text = line.strip()
    if not text:
        raise ConfigError(f'{source}:{lineno}: пустая строка роли')
    if ']' not in text:
        raise ConfigError(
            f'{source}:{lineno}: нужен формат "[id] название", нет "]": {line.strip()!r}')
    head, _, tail = text.partition(']')
    head = head.strip()
    if not head.startswith('['):
        raise ConfigError(
            f'{source}:{lineno}: нужен формат "[id] название", нет "[": {line.strip()!r}')
    raw_id = head[1:].strip()
    if not raw_id:
        raise ConfigError(f'{source}:{lineno}: пустой id роли: {line.strip()!r}')
    try:
        role_id = int(raw_id)
    except ValueError:
        raise ConfigError(
            f'{source}:{lineno}: некорректный id роли {raw_id!r} '
            f'(нужно целое число): {line.strip()!r}') from None
    return role_id, tail.strip()


def _load_roles() -> dict[int, Role]:
    roles: dict[int, Role] = {}
    seen: dict[int, int] = {}
    with open(ROLES_FILE, 'r', encoding='utf-8-sig') as f:
        for lineno, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            role_id, role_name = _parse_roles_line(raw, lineno, ROLES_FILE)
            if role_id in seen:
                raise ConfigError(
                    f'{ROLES_FILE}:{lineno}: дубль роли {role_id} '
                    f'(первое определение в строке {seen[role_id]})')
            seen[role_id] = lineno
            if not role_name:
                raise ConfigError(f'{ROLES_FILE}:{lineno}: пустое название роли {role_id}')
            roles[role_id] = Role(id=role_id, name=role_name)
    return roles


def _parse_employee_line(line: str, lineno: int, source: str) -> tuple[int, int, str, str]:
    """Разобрать 'id [role] фамилия имя' по любым пробельным разделителям (F19).

    Несколько пробелов/табуляция допустимы; позиции — по токенам split().
    Фамилия/имя могут отсутствовать (пустые строки).
    """
    parts = line.split()
    if len(parts) < 2:
        raise ConfigError(
            f'{source}:{lineno}: нужен формат "id [role] фамилия имя": {line.strip()!r}')
    try:
        emp_id = int(parts[0])
    except ValueError:
        raise ConfigError(
            f'{source}:{lineno}: некорректный id сотрудника {parts[0]!r}') from None
    role_tok = parts[1].strip()
    if not (role_tok.startswith('[') and role_tok.endswith(']')):
        raise ConfigError(
            f'{source}:{lineno}: роль должна быть в скобках "[id]": {parts[1]!r}')
    try:
        role_id = int(role_tok[1:-1].strip())
    except ValueError:
        raise ConfigError(
            f'{source}:{lineno}: некорректный id роли {parts[1]!r}') from None
    last_name = parts[2] if len(parts) > 2 else ''
    first_name = parts[3] if len(parts) > 3 else ''
    return emp_id, role_id, last_name, first_name


def _load_employees(roles: dict[int, Role] | None = None) -> dict[int, EmployeeData]:
    # R18: свежие roles передаются явно (иначе role_name брался из глобала
    # до его обновления — пустой на чистом старте, устаревший при повторе).
    if roles is None:
        roles = ROLES
    employees: dict[int, EmployeeData] = {}
    seen: dict[int, int] = {}
    with open(ID_EMPLOYEE_FILE, 'r', encoding='utf-8-sig') as f:
        for lineno, raw in enumerate(f, 1):
            if not raw.strip():
                continue
            emp_id, role_id, last_name, first_name = _parse_employee_line(
                raw, lineno, ID_EMPLOYEE_FILE)
            if emp_id in seen:
                raise ConfigError(
                    f'{ID_EMPLOYEE_FILE}:{lineno}: дубль сотрудника {emp_id} '
                    f'(первое определение в строке {seen[emp_id]})')
            seen[emp_id] = lineno
            role_name = roles[role_id].name if role_id in roles else ''
            employees[emp_id] = EmployeeData(
                id=emp_id, first_name=first_name, last_name=last_name,
                role_id=role_id, role_name=role_name,
            )
    # NOTE: ставки здесь НЕ подтягиваем: load_config() вызывается до
    # set_secret_key(), расшифровка дала бы stale-нули и лишний IO.
    # Актуальные rates грузит payroll_service один раз после ключа и передает явно.
    return employees


def _parse_wage_line(line: str, lineno: int, source: str) -> tuple[int, Decimal]:
    """Разобрать 'id [коп.руб]' → (id, расшифрованная ставка руб.коп).

    Разделители — любые пробельные (не только одиночный пробел, F19).
    Формат кода ставки: '[<коп>.<руб>]' наоборот, напр. '[867508.425]' → 425.867508.
    """
    parts = line.split()
    if len(parts) < 2:
        raise ConfigError(
            f'{source}:{lineno}: нужен формат "id [ставка]": {line.strip()!r}')
    try:
        emp_id = int(parts[0])
    except ValueError:
        raise ConfigError(
            f'{source}:{lineno}: некорректный id сотрудника {parts[0]!r}') from None
    tok = parts[1].strip()
    if not (tok.startswith('[') and tok.endswith(']')):
        raise ConfigError(
            f'{source}:{lineno}: ставка должна быть в скобках "[коп.руб]": {parts[1]!r}')
    raw_rate = tok[1:-1].strip()
    if '.' not in raw_rate:
        raise ConfigError(
            f'{source}:{lineno}: ставка {parts[1]!r} без точки (нужно "[коп.руб]")')
    kop, _, rub = raw_rate.partition('.')
    kop, rub = kop.strip(), rub.strip()
    if not kop or not rub:
        raise ConfigError(
            f'{source}:{lineno}: пустые копейки/рубли в ставке {parts[1]!r}')
    try:
        decrypted = Decimal(f'{rub}.{kop}')
    except InvalidOperation:
        raise ConfigError(
            f'{source}:{lineno}: некорректная ставка {parts[1]!r}') from None
    return emp_id, decrypted


def load_wage_rates(key: Decimal | float | str | None = None) -> dict[int, Decimal]:
    """Ставки в руб/смена 8ч как Decimal (до копеек, HALF_UP).

    Файл хранит переставленную запись 'коп.руб' -> расшифровка 'руб.коп'.
    Ключ передаётся явно (в памяти, F18); при key=None берётся текущий
    in-memory ключ (0.00, если не задан). На диск ничего не пишется.

    Ошибки формата/диапазона — ConfigError с файлом, строкой и полем;
    переполнение/неквантуемость ставки — тоже ConfigError до расчёта.
    """
    rates: dict[int, Decimal] = {}
    secret = as_decimal(key) if key is not None else get_secret_key()
    try:
        with open(WAGE_RATES_FILE, 'r', encoding='utf-8-sig') as f:
            lines = list(f)
    except (OSError, UnicodeDecodeError) as e:
        raise ConfigError(f'{WAGE_RATES_FILE}: не удалось прочитать ставки: {e}') from e
    seen_rates: dict[int, int] = {}
    for lineno, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        emp_id, decrypted = _parse_wage_line(raw, lineno, WAGE_RATES_FILE)
        if emp_id in seen_rates:
            raise ConfigError(
                f'{WAGE_RATES_FILE}:{lineno}: дубль ставки сотрудника {emp_id} '
                f'(первое определение в строке {seen_rates[emp_id]})')
        seen_rates[emp_id] = lineno
        try:
            rates[emp_id] = quantize_rate(decrypted * secret)
        except InvalidOperation as e:
            raise ConfigError(
                f'{WAGE_RATES_FILE}:{lineno}: ставка сотрудника {emp_id} '
                f'вне поддерживаемого диапазона (ключ×ставка не квантуется): {e}'
            ) from e
    return rates


def _load_settlement_exceptions() -> list[int]:
    exceptions: list[int] = []
    with open(SETTLEMENT_EXCEPTIONS_FILE, 'r', encoding='utf-8-sig') as f:
        for lineno, raw in enumerate(f, 1):
            text = raw.strip()
            if not text:
                continue
            # Допустимы пробельные разделители внутри строки: берём первый токен.
            tok = text.split()[0]
            try:
                exceptions.append(int(tok))
            except ValueError:
                raise ConfigError(
                    f'{SETTLEMENT_EXCEPTIONS_FILE}:{lineno}: '
                    f'некорректный id исключения {text!r}') from None
    return exceptions


#: In-memory ключ legacy-модели (Этап 7, F18). На диск не пишется.
_SECRET_KEY: Decimal | None = None


def get_secret_key() -> Decimal:
    """Текущий ключ из памяти запуска (0.00, если не задан).

    Совместимость: если память пуста, а legacy-файл остался от старой версии,
    он однократно читается в память и удаляется (миграция без потери ключа).
    Новые запуски файл не создают.
    """
    global _SECRET_KEY
    if _SECRET_KEY is not None:
        return _SECRET_KEY
    try:
        if os.path.exists(LEGACY_SECRET_FILE):
            with open(LEGACY_SECRET_FILE, 'r', encoding='utf-8') as f:
                _SECRET_KEY = as_decimal(f.read().strip())
            try:
                os.remove(LEGACY_SECRET_FILE)
            except OSError:
                pass
            return _SECRET_KEY
    except (OSError, ValueError, InvalidOperation, UnicodeDecodeError):
        pass
    return Decimal('0.00')


def _get_secret_key() -> Decimal:
    """Совместимость: раньше читал _secret_key.tmp, теперь — память."""
    return get_secret_key()


def set_secret_key(key: float | Decimal | str) -> None:
    """Запомнить ключ только в памяти запуска; legacy-файл удаляется (F18)."""
    global _SECRET_KEY
    _SECRET_KEY = as_decimal(key)
    try:
        if os.path.exists(LEGACY_SECRET_FILE):
            os.remove(LEGACY_SECRET_FILE)
    except OSError:
        pass


def clear_secret_key() -> None:
    """Сбросить in-memory ключ (для тестов/изоляции запусков)."""
    global _SECRET_KEY
    _SECRET_KEY = None
