from os import path
from contextlib import contextmanager
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

SECRET_FILE = '_secret_key.tmp'


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


def set_secret_file(file_path: str) -> None:
    """Переключить путь технического файла ключа (обычно в --output-dir)."""
    global SECRET_FILE
    SECRET_FILE = file_path


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


@contextmanager
def preserve_config():
    """Изолировать запуск, сохранив пути и объекты справочников для их потребителей."""
    path_keys = (
        'DATA_DIR', 'VARIABLE_DATA_DIR', 'ID_EMPLOYEE_FILE', 'ROLES_FILE',
        'WAGE_RATES_FILE', 'HOLIDAYS_FILE', 'POSTPONED_DAYS_FILE',
        'SETTLEMENT_EXCEPTIONS_FILE', 'SECRET_FILE',
    )
    saved_paths = {key: globals()[key] for key in path_keys}
    saved_roles, saved_employees = ROLES.copy(), EMPLOYEES.copy()
    saved_exceptions = SETTLEMENT_EXCEPTIONS.copy()
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
        clear_calendar_cache()


def load_config() -> None:
    # Сначала читаем весь набор: ошибка в одном файле не оставит смесь справочников.
    roles = _load_roles()
    employees = _load_employees(roles)
    exceptions = _load_settlement_exceptions()
    ROLES.clear()
    ROLES.update(roles)
    EMPLOYEES.clear()
    EMPLOYEES.update(employees)
    SETTLEMENT_EXCEPTIONS[:] = exceptions


def _load_roles() -> dict[int, Role]:
    roles: dict[int, Role] = {}
    with open(ROLES_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(']')
            role_id = int(parts[0].strip('['))
            role_name = parts[1].strip() if len(parts) > 1 else ''
            roles[role_id] = Role(id=role_id, name=role_name)
    return roles


def _load_employees(roles: dict[int, Role] | None = None) -> dict[int, EmployeeData]:
    if roles is None:
        roles = ROLES
    employees: dict[int, EmployeeData] = {}
    with open(ID_EMPLOYEE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            emp_id = int(parts[0])
            role_id = int(parts[1].strip('[]'))
            last_name = parts[2] if len(parts) > 2 else ''
            first_name = parts[3] if len(parts) > 3 else ''
            role_name = roles[role_id].name if role_id in roles else ''
            employees[emp_id] = EmployeeData(
                id=emp_id, first_name=first_name, last_name=last_name,
                role_id=role_id, role_name=role_name,
            )
    # NOTE: ставки здесь НЕ подтягиваем: load_config() вызывается до
    # set_secret_key(), расшифровка дала бы stale-нули и лишний IO.
    # Актуальные rates грузит payroll_service один раз после ключа и передает явно.
    return employees


def load_wage_rates() -> dict[int, Decimal]:
    """Ставки в руб/смена 8ч как Decimal (до копеек, HALF_UP).

    Файл хранит переставленную запись 'коп.руб' -> расшифровка 'руб.коп'.
    Раньше было round(float * key) до целых рублей — терялись копейки
    и вносилась binary-ошибка float. Теперь Decimal со строковым парсингом.
    """
    rates: dict[int, Decimal] = {}
    key = _get_secret_key()
    with open(WAGE_RATES_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            emp_id = int(parts[0])
            raw_rate = parts[1].strip('[]')
            rate_parts = raw_rate.split('.')
            decrypted = Decimal(rate_parts[1] + '.' + rate_parts[0])
            rates[emp_id] = quantize_rate(decrypted * key)
    return rates


def _load_settlement_exceptions() -> list[int]:
    exceptions: list[int] = []
    with open(SETTLEMENT_EXCEPTIONS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                exceptions.append(int(line))
    return exceptions


def _get_secret_key() -> Decimal:
    try:
        with open(SECRET_FILE, 'r') as f:
            return as_decimal(f.read().strip())
    except (FileNotFoundError, ValueError, InvalidOperation):
        return Decimal('0.00')


def set_secret_key(key: float | Decimal | str) -> None:
    with open(SECRET_FILE, 'w') as f:
        f.write(str(as_decimal(key)))
