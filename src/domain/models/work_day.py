
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Tuple


class DayStatus(Enum):
    """Work day status"""
    NORMAL = "normal"
    SHORT = "short"
    ABSENT = "absent"
    OVERTIME = "overtime"


class DayType(Enum):
    """Day type by calendar"""
    WORKDAY = "workday"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


@dataclass(frozen=True)
class TimeRecord:
    """Одна отметка времени. Объект-значение."""
    timestamp: datetime


@dataclass(frozen=True)
class WorkDay:
    """
    Рабочий день. Является локальной сущностью внутри агрегата WorkPeriod.
    Этот объект неизменяем.
    """
    date: date
    day_type: DayType
    time_records: Tuple[TimeRecord, ...] = field(default_factory=tuple)

    def add_record(self, record: TimeRecord) -> "WorkDay":
        """
        Возвращает новый экземпляр WorkDay с добавленной отметкой времени.
        """
        if record.timestamp.date() != self.date:
            raise ValueError("Record date does not match WorkDay date.")

        updated_records = sorted(self.time_records + (record,), key=lambda r: r.timestamp)
        return WorkDay(
            date=self.date,
            day_type=self.day_type,
            time_records=tuple(updated_records),
        )
