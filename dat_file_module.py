import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logging.basicConfig(
    filename="logs.txt",          # Логируем в файл
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

@dataclass
class AttendanceRecord:
    """
    Хранит информацию об одной записи посещения.

    Поля:
    - employee_id: идентификатор сотрудника
    - timestamp: дата и время метки (datetime)
    - raw_line: исходная строка из .dat (для удобства аудита/логирования)
    """
    employee_id: int
    timestamp: datetime
    raw_line: str

class DatFileProcessor:
    """
    Класс для чтения, парсинга и валидации данных из .dat файла.
    """
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def _is_record_in_target_period(self, record: AttendanceRecord,target_period:tuple) -> bool:
        """
        Проверяет, попадает ли запись в целевой период.
        :param record: Объект AttendanceRecord.
        :return: True, если запись в целевом периоде, иначе False.
        """
        if target_period is not None:
            year = target_period[0]
            month = target_period[1]
            record_date = record.timestamp.date()
            if record_date.year == year and record_date.month == month:
                return True
            else:
                return False
        else:
            return True

    def read_dat_file(self, file_path: str, target_period: Optional[tuple] = None) -> List[AttendanceRecord]:
        """
        Основной метод для чтения .dat файла и конвертации строк в объекты AttendanceRecord.
        :param file_path: Путь к .dat файлу.
        :return: Список валидных записей AttendanceRecord.
        """
        records = []

        if not os.path.exists(file_path):
            logging.error(f"Файл не найден: {file_path}")
            # Можно либо вернуть пустой список, либо выбросить исключение.
            return records

        try:
            with open(file_path, "r", encoding="utf-8") as dat_file:
                for line_number, line in enumerate(dat_file, start=1):
                    line = line.strip()
                    if not line:
                        # Пропускаем пустые строки
                        continue

                    record = self._parse_line(line, line_number)
                    if record and self._is_record_in_target_period(record,target_period):
                        records.append(record)

            logging.info(f"Файл '{file_path}' успешно прочитан. Всего записей: {len(records)}.")

        except Exception as e:
            logging.exception(f"Ошибка при чтении файла '{file_path}': {e}")

        return records

    def _parse_line(self, line: str, line_number: int) -> Optional[AttendanceRecord]:
        """
        Парсит одну строку из .dat файла, возвращает объект AttendanceRecord или None при ошибке.
        """
        parts = line.split("\t")

        # Ожидаем минимум 2 колонки: ID и Дата/Время
        if len(parts) < 2:
            logging.warning(f"[Строка {line_number}] Недостаточно полей. Исходная строка: '{line}'")
            return None

        # Парсим employee_id
        try:
            employee_id = int(parts[0])
        except ValueError:
            logging.warning(f"[Строка {line_number}] Невозможно преобразовать ID в int. Строка: '{line}'")
            return None

        # Парсим дату/время
        datetime_str = parts[1]
        try:
            timestamp = datetime.strptime(datetime_str, self.DATETIME_FORMAT)
        except ValueError:
            logging.warning(f"[Строка {line_number}] Неверный формат даты/времени '{datetime_str}'. Строка: '{line}'")
            return None

        # Создаём запись
        return AttendanceRecord(
            employee_id=employee_id,
            timestamp=timestamp,
            raw_line=line
        )