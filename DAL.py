###В этом модуле описывается слой доступа к данным (DAL)
###Данные могут быть получены из файла - если они новые, или из БД, если они уже были загружены
import os
from datetime import datetime
from typing import List, Optional

# Пример DTO (Data Transfer Object) для одной отметки
class AttendanceRecord:
    def __init__(self, employee_id: int, dt: datetime):
        self.employee_id = employee_id
        self.dt = dt
    
    def __repr__(self):
        return f"<AttendanceRecord id={self.employee_id}, dt={self.dt.isoformat()}>"


class DualDataAccess:
    """
    Класс, который проверяет наличие файла 1_attlog.dat;
    - если файл существует — читает из файла;
    - иначе читает из базы.
    """

    def __init__(self, file_name: str = "1_attlog.dat", db=None):
        """
        :param file_name: Имя файла с «сырыми» отметками
        :param db: Ссылка/объект на класс, управляющий доступом к базе данных (можете передать свой DAL)
        """
        self.file_name = file_name
        self.db = db  # Тут можно передать ваш класс, который работает с базой (DataAccessDB, Session и т.д.)

    def get_attendance_for_month(self, year: int, month: int) -> List[AttendanceRecord]:
        """
        Метод «отдаёт» список AttendanceRecord за указанный год и месяц.
        Сначала проверяет наличие файла. 
        Если файл найден — читаем из него. 
        Если файла нет — идём в базу данных.
        """

        if os.path.exists(self.file_name):
            # Читаем из файла
            print(f"[DualDataAccess] Найден файл {self.file_name}. Читаем данные из файла.")
            return self._read_from_file(year, month)
        else:
            # Читаем из базы данных
            print(f"[DualDataAccess] Файл {self.file_name} не найден. Читаем данные из БД.")
            return self._read_from_db(year, month)

    def _read_from_file(self, year: int, month: int) -> List[AttendanceRecord]:
        """
        Внутренний метод для чтения данных из файла за нужный год/месяц.
        Можно взять вашу реализацию read_file_data + build_data_array 
        и просто адаптировать под логику возврата списка объектов.
        """
        result: List[AttendanceRecord] = []
        with open(self.file_name, "r", encoding="utf-8") as f:
            for line in f:
                # Здесь можно вызвать вашу существующую функцию фильтра,
                # например determination_period(line, year, month)
                # Или «на лету» парсить строку
                if self._belongs_to_period(line, year, month):
                    # создаём объект AttendanceRecord
                    record = self._parse_line_to_record(line)
                    if record:
                        result.append(record)
        return result

    def _belongs_to_period(self, line: str, year: int, month: int) -> bool:
        """
        Проверяем, относится ли данная строка к нужному году/месяцу.
        (Упрощённая логика, вы можете использовать свою determination_period(line, ...) )
        """
        parts = line.strip().split()
        if len(parts) < 2:
            return False
        try:
            date_str = parts[1]  # допустим, '2021-03-01'
            y = int(date_str[:4])
            m = int(date_str[5:7])
            return (y == year and m == month)
        except ValueError:
            return False

    def _parse_line_to_record(self, line: str) -> Optional[AttendanceRecord]:
        """
        Преобразует строку файла в объект AttendanceRecord.
        """
        parts = line.strip().split()
        if len(parts) < 3:
            return None

        try:
            employee_id = int(parts[0])
            date_str = parts[1]  # '2021-03-01'
            time_str = parts[2]  # '06:30:00', и т.д.
            dt_str = date_str + " " + time_str
            dt_obj = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

            return AttendanceRecord(employee_id, dt_obj)
        except ValueError:
            return None

    def _read_from_db(self, year: int, month: int) -> List[AttendanceRecord]:
        """
        Внутренний метод для чтения из базы данных.
        Предполагается, что self.db предоставляет метод получения записей за год/месяц.
        """
        if not self.db:
            # Если db=None, можно вернуть пустой список или выбросить исключение.
            print("[DualDataAccess] db не инициализирован, возвращаем пустой список.")
            return []
        
        # Допустим, в self.db есть метод: get_attendance_for_month(year, month) -> List[AttendanceRecord]
        return self.db.get_attendance_for_month(year, month)

    # При желании можете добавить метод сохранения, 
    # который тоже будет смотреть — если файл есть, значит сохраняем в файл, 
    # либо (или вместе) — сохраняем в БД.


# ============ Пример использования ============
if __name__ == "__main__":
    # Допустим, у нас есть некий объект DB — класс, работающий с базой (можно замокать).
    fake_db = None  # В реальности вы используете свой класс DataAccessDB, например.

    dal = DualDataAccess(file_name="1_attlog.dat", db=fake_db)

    records_march = dal.get_attendance_for_month(2021, 3)
    print("Результат чтения:", records_march)
