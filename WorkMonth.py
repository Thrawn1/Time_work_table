import datetime
import calendar
import toml

class WorkMonth():
    def __init__(self, year:int, month:int):
        self.year = year
        self.month = month
        self.workdays = self._get_workdays(year, month)
        self.weekends = self._get_weekends(month, year)
        

    def _get_workdays(self,year:int,month:int) -> None:
        """
        Возвращает список рабочих дней в месяце.
        """
        _, days_in_month = calendar.monthrange(year, month)
        return [day for day in range(1, days_in_month + 1) 
                         if calendar.weekday(year, month, day) < 5]


    def _get_weekends(self,month:int,year:int) -> None:
        """
        Возвращает список выходных дней в месяце.
        """
        _, days_in_month = calendar.monthrange(year,month)
        return [day for day in range(1, days_in_month + 1) 
                         if calendar.weekday(self.year, self.month, day) >= 5]

    def _insert_holidays(self) -> None:
        """
        Убирает рабочие дни из списка рабочих дней и вставляет их в список выходных дней, используя
        файл holidays.toml.
        """
        holidays = toml.load('holidays.toml')
        for holiday in holidays:
            if holiday['date'].year == self.year and holiday['date'].month == self.month:
                if holiday['type'] == 'holiday':
                    self.workdays.remove(holiday['date'].day)
                    self.weekends.append(holiday['date'].day)
                elif holiday['type'] == 'weekend':
                    self.workdays.remove(holiday['date'].day)
                    self.weekends.append(holiday['date'].day)
    def _insert_postponed(self) -> None:
        """
        Убирает выходные дни из списка выходных дней и вставляет их в список рабочих дней, используя
        файл postponed_day.toml.
        """
        postponed = toml.load('postponed_day.toml')
        for day in postponed:
            if day['date'].year == self.year and day['date'].month == self.month:
                if day['type'] == 'holiday':
                    self.weekends.remove(day['date'].day)
                    self.workdays.append(day['date'].day)
                elif day['type'] == 'weekend':
                    self.weekends.remove(day['date'].day)
                    self.workdays.append(day['date'].day)
    
    def get_all_days_work_month(self) -> dict[str, list[int]]:
        """
        Возвращает список всех дней месяца, разбивая на рабочие и выходные согласно 
        производсвтенному календарю.
        """
        return {
            'workdays': self.workdays,
            'weekends': self.weekends
        }