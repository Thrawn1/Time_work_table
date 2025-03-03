from datetime import date as DT_date
from calendar import monthrange, weekday
from toml import load as TOML_load
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("workmonth.log"),
        logging.StreamHandler()
    ]
)

class WorkMonth():
    def __init__(self, year:int, month:int):
        self.logger = logging.getLogger('WorkMonth')
        self.logger.info("Инициализация объекта WorkMonth")
        
        if not (1 <= month <= 12):
            self.logger.error(f"Неверный номер месяца: {month}")
            raise ValueError(f"Неверный номер месяца: {month}. Ожидалось число от 1 до 12.")
        if not (2015 <= year <= 2100):
            self.logger.error(f"Неверный год: {year}")
            raise ValueError(f"Неверный год: {year}. Ожидалось число от 2015 до 2100.")
        
        self.year = year
        self.month = month
        
        self.logger.info(f"Инициализация рабочего месяца {month}.{year}")
        
        self.workdays = self._get_workdays(year, month)
        self.weekends = self._get_weekends(year, month)
        
        self._insert_holidays()
        self._insert_postponed()
        
        self.logger.info(f"Месяц {month}.{year} инициализирован. Рабочих дней: {len(self.workdays)}, выходных: {len(self.weekends)}")

    def _load_toml(self, file_name: str) -> list[DT_date]:
        """
        Загружает даты из файла TOML и возвращает их в виде списка объектов datetime.date.
        """
        try:
            self.logger.debug(f"Попытка загрузки файла {file_name}")
            dates = TOML_load(file_name)
            if not isinstance(dates, list):
                self.logger.error(f"Ошибка чтения {file_name}: ожидался список дат, получен {type(dates)}")
                raise ValueError(f"Ошибка чтения {file_name}: ожидался список дат, получен {type(dates)}.")
            if dates and "date" not in dates[0]:
                self.logger.error(f"Ошибка чтения {file_name}: отсутствует ключ 'date'")
                raise ValueError(f"Ошибка чтения {file_name}: отсутствует ключ 'date'.")
            self.logger.info(f"Файл {file_name} успешно загружен, найдено {len(dates)} записей")
            return dates
        except FileNotFoundError:
            self.logger.warning(f"Файл {file_name} не найден. Продолжаем без этих дат.")
            return []
        except Exception as e:
            self.logger.error(f"Ошибка чтения {file_name}: {str(e)}")
            return []

    def _get_workdays(self, year: int, month: int) -> list[DT_date]:
        """
        Возвращает список рабочих дней в месяце как объекты datetime.date.
        """
        _, days_in_month = monthrange(year, month)
        workdays = [DT_date(year, month, day) for day in range(1, days_in_month + 1) 
                if weekday(year, month, day) < 5]
        self.logger.debug(f"Определено {len(workdays)} стандартных рабочих дней")
        return workdays

    def _get_weekends(self, year: int,month: int) -> list[DT_date]:
        """
        Возвращает список выходных дней в месяце как объекты datetime.date.
        """
        _, days_in_month = monthrange(year, month)
        weekends = [DT_date(year, month, day) for day in range(1, days_in_month + 1) 
                if weekday(year, month, day) >= 5]
        self.logger.debug(f"Определено {len(weekends)} стандартных выходных дней")
        return weekends

    def _insert_holidays(self) -> None:
        """
        Убирает рабочие дни из списка рабочих дней и вставляет их в список выходных дней, используя
        файл holidays.toml.
        """
        self.logger.info("Обработка праздничных дней")
        holidays = self._load_toml('holidays.toml')
        holidays_count = 0
        
        for holiday in holidays:
            holiday_date = holiday.get('date')
            if not holiday_date:
                self.logger.error("Ошибка чтения holidays.toml: отсутствует ключ 'date'")
                continue
            if holiday_date.year == self.year and holiday_date.month == self.month:
                if holiday_date in self.workdays:
                    self.workdays.remove(holiday_date)
                    self.weekends.append(holiday_date)
                    holidays_count += 1
                    self.logger.debug(f"Добавлен праздник: {holiday_date}")
                else:
                    self.logger.warning(f"Дата {holiday_date} не найдена в списке рабочих дней")
        
        self.logger.info(f"Добавлено {holidays_count} праздничных дней")

    def _insert_postponed(self) -> None:
        """
        Убирает выходные дни из списка выходных дней и вставляет их в список рабочих дней, используя
        файл postponed_day.toml.
        """
        self.logger.info("Обработка перенесенных дней")
        postponed = self._load_toml('postponed_day.toml')
        postponed_count = 0
        
        for postponed_day in postponed:
            postponed_date = postponed_day.get('date')
            if not postponed_date:
                self.logger.error("Ошибка чтения postponed_day.toml: отсутствует ключ 'date'")
                continue
            if postponed_date.year == self.year and postponed_date.month == self.month:
                if postponed_date in self.weekends:
                    self.weekends.remove(postponed_date)
                    self.workdays.append(postponed_date)
                    postponed_count += 1
                    self.logger.debug(f"Добавлен рабочий день: {postponed_date}")
                else:
                    self.logger.warning(f"Дата {postponed_date} не найдена в списке выходных дней")
        
        self.logger.info(f"Добавлено {postponed_count} рабочих дней из переносов")

    def get_all_days_work_month(self) -> dict[str, list[DT_date]]:
        """
        Возвращает список всех дней месяца, разбивая на рабочие и выходные согласно 
        производсвтенному календарю.
        """
        self.logger.debug("Получен запрос на все дни месяца")
        return {
            'workdays': self.workdays,
            'weekends': self.weekends
        }