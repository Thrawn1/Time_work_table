from os import path
from dataclasses import dataclass

DATA_DIR = 'data'
VARIABLE_DATA_DIR = path.join(DATA_DIR, 'variable_data_for_app')

ID_EMPLOYEE_FILE = path.join(VARIABLE_DATA_DIR, 'id_employee.dat')
ROLES_FILE = path.join(VARIABLE_DATA_DIR, 'roles_employee.dat')
WAGE_RATES_FILE = path.join(VARIABLE_DATA_DIR, 'wage_rates.dat')
HOLIDAYS_FILE = path.join(VARIABLE_DATA_DIR, 'holidays.dat')
POSTPONED_DAYS_FILE = path.join(VARIABLE_DATA_DIR, 'postponed_working_days.dat')
SETTLEMENT_EXCEPTIONS_FILE = path.join(VARIABLE_DATA_DIR, 'settlement_exceptions.dat')
TOML_CONFIG_FILE = 'company_data_real.toml'
DEFAULT_ATTLOG_FILE = path.join(DATA_DIR, '1_attlog.dat')


@dataclass
class Role:
    id: int
    name: str
    work_shift: int = 8
    lost_tag_flag: int = 1


@dataclass
class EmployeeData:
    id: int
    first_name: str
    last_name: str
    role_id: int
    role_name: str
    hourly_rate: float


ROLES: dict[int, Role] = {}
EMPLOYEES: dict[int, EmployeeData] = {}
SETTLEMENT_EXCEPTIONS: list[int] = []


def load_config() -> None:
    ROLES.clear()
    ROLES.update(_load_roles())
    EMPLOYEES.clear()
    EMPLOYEES.update(_load_employees())
    SETTLEMENT_EXCEPTIONS.clear()
    SETTLEMENT_EXCEPTIONS.extend(_load_settlement_exceptions())


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


def _load_employees() -> dict[int, EmployeeData]:
    employees: dict[int, EmployeeData] = {}
    with open(ID_EMPLOYEE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(' ')
            emp_id = int(parts[0])
            role_id = int(parts[1].strip('[]'))
            last_name = parts[2] if len(parts) > 2 else ''
            first_name = parts[3] if len(parts) > 3 else ''
            role_name = ROLES[role_id].name if role_id in ROLES else ''
            employees[emp_id] = EmployeeData(
                id=emp_id, first_name=first_name, last_name=last_name,
                role_id=role_id, role_name=role_name, hourly_rate=0,
            )
    rates = load_wage_rates()
    for emp_id, rate in rates.items():
        if emp_id in employees:
            employees[emp_id].hourly_rate = rate
    return employees


def load_wage_rates() -> dict[int, float]:
    rates: dict[int, float] = {}
    key = _get_secret_key()
    with open(WAGE_RATES_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(' ')
            emp_id = int(parts[0])
            raw_rate = parts[1].strip('[]')
            rate_parts = raw_rate.split('.')
            decrypted = float(rate_parts[1] + '.' + rate_parts[0])
            rates[emp_id] = round(decrypted * key)
    return rates


def _load_settlement_exceptions() -> list[int]:
    exceptions: list[int] = []
    with open(SETTLEMENT_EXCEPTIONS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                exceptions.append(int(line))
    return exceptions


def _get_secret_key() -> float:
    try:
        with open('_secret_key.tmp', 'r') as f:
            return float(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0.0


def set_secret_key(key: float) -> None:
    with open('_secret_key.tmp', 'w') as f:
        f.write(str(key))
