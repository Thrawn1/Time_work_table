from dataclasses import dataclass
from datetime import date, time, datetime
from core.constants import MONTHS_NAME_TO_RUSSIAN, WEEKDAYS_NAME


@dataclass
class Mark:
    """Метка прихода/ухода с датчика."""
    mark_date: date
    mark_time: time
    flag: int = 0  # 0 = приход, 1 = уход

    @classmethod
    def from_raw_line(cls, line: str) -> 'Mark':
        mark_date = date.fromisoformat(line[10:20])
        mark_time = time.fromisoformat(line[21:29])
        return cls(mark_date=mark_date, mark_time=mark_time, flag=0)

    def set_flag(self, value: int) -> None:
        self.flag = value

    @property
    def day(self) -> int:
        return self.mark_date.day

    def __str__(self) -> str:
        flag_names = {0: 'Приход', 1: 'Уход', 3: 'Не определен'}
        return f'{flag_names.get(self.flag, "Не определен")}, Время отметки: {self.mark_time}'


@dataclass
class WorkDay:
    """Данные за один рабочий день."""
    year: int
    month: int
    day: int
    day_of_week: str
    month_name: str
    mark_come: Mark
    mark_go: Mark

    @classmethod
    def from_mark(cls, first_mark: Mark) -> 'WorkDay':
        d = first_mark.mark_date
        return cls(
            year=d.year, month=d.month, day=d.day,
            day_of_week=WEEKDAYS_NAME[d.weekday()],
            month_name=MONTHS_NAME_TO_RUSSIAN[d.month],
            mark_come=first_mark, mark_go=first_mark,
        )

    def has_lost_mark(self) -> bool:
        return self.mark_come.flag == self.mark_go.flag

    def edit_mark(self, flag: int, new_time_str: str) -> None:
        from datetime import time as t
        new_time = t.fromisoformat(new_time_str)
        if flag == 0 or new_time < self.mark_go.mark_time:
            self.mark_come.mark_time = new_time
        elif flag == 1:
            self.mark_go.mark_time = new_time

    def __str__(self) -> str:
        return f'{self.day} {self.month_name} {self.year} - {self.day_of_week}'
