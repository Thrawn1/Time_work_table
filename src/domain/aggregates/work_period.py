
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Tuple

from domain.models.work_day import DayType, TimeRecord, WorkDay
from domain.value_objects.identifiers import EmployeeId


@dataclass
class WorkPeriod:
    """
    Рабочий период сотрудника (например, месяц). Корень агрегата.
    """
    employee_id: EmployeeId  # Ссылка на агрегат Employee по ID
    period_start: date
    period_end: date

    # Список дней делаем "приватным" по соглашению Python
    _work_days: List[WorkDay] = field(default_factory=list)

    @property
    def work_days(self) -> Tuple[WorkDay, ...]:
        """Публичное свойство для безопасного чтения рабочих дней."""
        return tuple(self._work_days)

    def add_time_record(self, timestamp: datetime, day_type: DayType):
        """
        Главный метод для добавления отметки времени.
        Он защищает инварианты (бизнес-правила) этого агрегата.
        """
        record_date = timestamp.date()

        # Инвариант №1: Отметка времени не может быть вне расчетного периода.
        if not (self.period_start <= record_date <= self.period_end):
            raise ValueError("Timestamp date is outside the work period.")

        # Находим существующий день или создаем новый.
        day_to_update = self._find_or_create_day(record_date, day_type)

        # Так как WorkDay теперь тоже будет неизменяемым, мы создаем новый
        # объект WorkDay с добавленной отметкой времени.
        updated_day = day_to_update.add_record(TimeRecord(timestamp))

        # Заменяем старый объект дня на новый в нашем списке.
        self._work_days = [
            d for d in self._work_days if d.date != record_date
        ]
        self._work_days.append(updated_day)
        # Поддерживаем порядок для предсказуемости.
        self._work_days.sort(key=lambda d: d.date)

    def _find_or_create_day(self, day_date: date, day_type: DayType) -> WorkDay:
        """Внутренний вспомогательный метод для поиска или создания дня."""
        existing_day = next((d for d in self._work_days if d.date == day_date), None)
        if existing_day:
            return existing_day
        else:
            # Инвариант №2: Создаем день, только если его еще нет.
            return WorkDay(date=day_date, day_type=day_type, time_records=())
