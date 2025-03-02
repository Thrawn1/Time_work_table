from datetime import date as DT_date
from calendar import monthrange, weekday
from toml import load as TOML_load

class WorkMonth():
    def __init__(self, year:int, month:int):
        self.year = year
        self.month = month
        self.workdays = self._get_workdays(year, month)
        self.weekends = self._get_weekends(month, year)
        self._insert_holidays()
        self._insert_postponed()

    def _get_workdays(self, year: int, month: int) -> list[DT_date]:
        """
        Возвращает список рабочих дней в месяце как объекты datetime.date.
        """
        _, days_in_month = monthrange(year, month)
        return [DT_date(year, month, day) for day in range(1, days_in_month + 1) 
                if weekday(year, month, day) < 5]

    def _get_weekends(self, year: int,month: int) -> list[DT_date]:
        """
        Возвращает список выходных дней в месяце как объекты datetime.date.
        """
        _, days_in_month = monthrange(year, month)
        return [DT_date(year, month, day) for day in range(1, days_in_month + 1) 
                if weekday(year, month, day) >= 5]

    def _insert_holidays(self) -> None:
        """
        Убирает рабочие дни из списка рабочих дней и вставляет их в список выходных дней, используя
        файл holidays.toml.
        """
        try:
            holidays = TOML_load('holidays.toml')
        except FileNotFoundError:
            print("Внимание: файл holidays.toml не найден. Продолжаем без праздничных дней.")
            holidays = []
        except Exception as e:
            print(f"Ошибка чтения holidays.toml: неверный формат TOML. {str(e)}")
            holidays = []
        try:
            holidays[0]['date']
        except KeyError:
            print("Ошибка чтения holidays.toml: неверный формат TOML. Отсутствует ключ 'date'.")
            holidays = []

        for holiday in holidays:
            holiday_date = holiday['date']
            if holiday_date.year == self.year and holiday_date.month == self.month:
                if holiday_date in self.workdays:
                    self.workdays.remove(holiday_date)
                    self.weekends.append(holiday_date)
                else:
                    print(f"Ошибка чтения holidays.toml: дата {holiday_date} не найдена в списке рабочих дней.")
    def _insert_postponed(self) -> None:
        """
        Убирает выходные дни из списка выходных дней и вставляет их в список рабочих дней, используя
        файл postponed_day.toml.
        """
        try:
            postponed = TOML_load('postponed_day.toml')
        except FileNotFoundError:
            print("Внимание: файл postponed_day.toml не найден. Продолжаем без перенесенных дней.")
            postponed = []
        except Exception as e:
            print(f"Ошибка чтения postponed_day.toml: неверный формат TOML. {str(e)}")  
            postponed = []

        try:
            postponed[0]['date']
        except KeyError:
            print("Ошибка чтения postponed_day.toml: неверный формат TOML. Отсутствует ключ 'date'.")
            postponed = []
        for day in postponed:
            postponed_date = day['date']
            if postponed_date.year == self.year and postponed_date.month == self.month:
                if postponed_date in self.weekends:
                    self.weekends.remove(postponed_date)
                    self.workdays.append(postponed_date)
                else:
                    print(f"Ошибка чтения postponed_day.toml: дата {postponed_date} не найдена в списке выходных дней.")
    
    def get_all_days_work_month(self) -> dict[str, list[DT_date]]:
        """
        Возвращает список всех дней месяца, разбивая на рабочие и выходные согласно 
        производсвтенному календарю.
        """
        return {
            'workdays': self.workdays,
            'weekends': self.weekends
        }