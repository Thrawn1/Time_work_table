from datetime import date as DT_date
from calendar import monthrange, weekday
from toml import load as TOML_load

class WorkMonth():
    def __init__(self, year:int, month:int):
        if not (1 <= month <= 12):
            raise ValueError(f"Неверный номер месяца: {month}. Ожидалось число от 1 до 12.")
        if not (2015 <= year <= 2100):
            raise ValueError(f"Неверный год: {year}. Ожидалось число от 2015 до 2100.")
        
        self.year = year
        self.month = month
        
        self.workdays = self._get_workdays(year, month)
        self.weekends = self._get_weekends(month, year)
        
        self._insert_holidays()
        self._insert_postponed()

    def _load_toml(self, file_name: str) -> list[DT_date]:
        """
        Загружает даты из файла TOML и возвращает их в виде списка объектов datetime.date.
        """
        try:
            dates = TOML_load(file_name)
            if not isinstance(dates, list):
                raise ValueError(f"Ошибка чтения {file_name}: ожидался список дат, получен {type(dates)}.")
            if dates and "date" not in dates[0]:
                raise ValueError(f"Ошибка чтения {file_name}: отсутствует ключ 'date'.")
            return dates
        except FileNotFoundError:
            print(f"Внимание: файл {file_name} не найден. Продолжаем без праздничных дней.")
            return []
        except Exception as e:
            print(f"Ошибка чтения {file_name}: {str(e)}")
            return []

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
        holidays = self._load_toml('holidays.toml')
        for holiday in holidays:
            holiday_date = holiday.get('date')
            if not holiday_date:
                print("Ошибка чтения holidays.toml: отсутствует ключ 'date'.")
                continue
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
        postponed = self._load_toml('postponed_day.toml')
        for postponed_day in postponed:
            postponed_date = postponed_day.get('date')
            if not postponed_date:
                print("Ошибка чтения postponed_day.toml: отсутствует ключ 'date'.")
                continue
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