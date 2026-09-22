"""Синтетические DAT-справочники для тестов (R22).

Маленький фиксированный набор вместо рабочих данных: тесты не зависят от
состава реальных сотрудников и не ломаются при изменении рабочих справочников.
Рабочие `data/*.dat`, `company.db`, `wage_rates.dat` в тестах не используются.
"""

from pathlib import Path

ROLES_TXT = """\
[0] Руководитель
[1] Работник цеха
[2] Кладовщик
[3] Проживающий в цеху
[4] Ремонтники
"""

EMPLOYEES_TXT = """\
1 [1] Цеховик А
2 [2] Кладовщик К
3 [3] Проживающий П
4 [4] Ремонтник Р
7 [0] Руководитель Д
"""

EXCEPTIONS_TXT = """\
3
"""


def write_synth_dat_dir(path) -> str:
    """Записать синтетические справочники в каталог, вернуть путь строкой."""
    d = Path(path)
    d.mkdir(parents=True, exist_ok=True)
    (d / 'roles_employee.dat').write_text(ROLES_TXT, encoding='utf-8')
    (d / 'id_employee.dat').write_text(EMPLOYEES_TXT, encoding='utf-8')
    (d / 'settlement_exceptions.dat').write_text(EXCEPTIONS_TXT, encoding='utf-8')
    return str(d)
