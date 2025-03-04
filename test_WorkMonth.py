import pytest
from datetime import date
from unittest.mock import patch
from WorkMonth import WorkMonth

#
# 1. Тесты конструктора
#

def test_workmonth_correct_init():
    """Проверяем, что корректные год и месяц не вызывают ошибок."""
    w = WorkMonth(2023, 3)
    assert w.year == 2023
    assert w.month == 3
    # Убедимся, что список рабочих дней не пуст
    assert len(w.workdays) > 0
    assert len(w.weekends) > 0

def test_workmonth_incorrect_month():
    """Проверяем, что при некорректном месяце вызывается ValueError."""
    with pytest.raises(ValueError) as excinfo:
        WorkMonth(2023, 13)  # Месяц 13
    assert "Неверный номер месяца" in str(excinfo.value)

def test_workmonth_incorrect_year():
    """Проверяем, что при некорректном годе вызывается ValueError."""
    with pytest.raises(ValueError) as excinfo:
        WorkMonth(2101, 1)   # Год 2101
    assert "Неверный год" in str(excinfo.value)

#
# 2. Тестирование заполнения рабочих/выходных дней
#

def test_workdays_and_weekends_count():
    """Проверяем общее число дней в месяце и распределение их на будни/выходные."""
    w = WorkMonth(2023, 1)  # Январь 2023
    all_days = w.get_all_days_work_month()
    total_days = len(all_days['workdays']) + len(all_days['weekends'])

    # Январь 2023 имеет 31 день
    assert total_days == 31

    # Для января 2023 можем проверить конкретное соотношение
    # (будни/выходные можно уточнить, если нужно)
    # Но достаточно проверить, что нет пересечений списков:
    intersection = set(all_days['workdays']) & set(all_days['weekends'])
    assert len(intersection) == 0

#
# 3. Тестирование праздничных дней
#    Для этого замокаем (подделаем) результат чтения из файла holidays.toml.
#

@patch('WorkMonth.TOML_load')
def test_insert_holidays(mock_toml_load):
    """
    Проверяем, что день, помеченный в holidays.toml,
    переносится из workdays в weekends.
    """
    # Допустим, в holidays.toml была записана только 1 января 2023
    mock_toml_load.return_value = [
        {'date': date(2023, 1, 1)}
    ]
    w = WorkMonth(2023, 1)
    
    # В январе 2023 1 число — это воскресенье.
    # Обычно оно и так выходной, но представим, что был сбой, и
    # наша логика должна что-то поменять (или хотя бы проверить).
    # Посмотрим, есть ли 1 января в списке weekends:
    assert date(2023, 1, 1) in w.weekends

    # Можем проверить, что в логи вывелось сообщение о том,
    # что этот день не найден в списке рабочих (warning).
    # Но это проверка логов — уже другая задача.
    # Здесь важно, что код не упал.

#
# 4. Тестирование перенесённых дней (postponed_day.toml)
#

@patch('WorkMonth.TOML_load')
def test_insert_postponed(mock_toml_load):
    """
    Проверяем, что перенесённый (постановлением) выходной становится рабочим днём.
    """
    # Допустим, 7 января 2023 (суббота) официально перенесли как рабочий день
    mock_toml_load.return_value = [
        {'date': date(2023, 1, 7)}
    ]
    w = WorkMonth(2023, 1)

    # 7 января 2023 — это выходной (суббота),
    # значит, после переноса он должен оказаться в workdays
    assert date(2023, 1, 7) in w.workdays
    assert date(2023, 1, 7) not in w.weekends

#
# 5. Проверка, что при отсутствии файла TOML работа идёт без ошибок
#    (load_toml вернёт пустой список).
#

@patch('WorkMonth.TOML_load', side_effect=FileNotFoundError("test"))
def test_file_not_found(mock_toml_load):
    """Если файл не найден, просто игнорируем праздники/переносы и всё работает."""
    w = WorkMonth(2023, 2)
    # Убедимся, что конструктор успешно отработал без выброса исключений
    all_days = w.get_all_days_work_month()
    assert len(all_days['workdays']) > 0
    assert len(all_days['weekends']) > 0
