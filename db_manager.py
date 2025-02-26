# db_manager.py

import sqlite3

class DBManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """
        Создаёт таблицу employees, если она ещё не существует.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id      INTEGER PRIMARY KEY,
                    first_name       TEXT,
                    last_name        TEXT,
                    role             TEXT,
                    hourly_rate      REAL,
                    role_coefficient REAL DEFAULT 1.0
                );
            """)
            conn.commit()

    def add_employee(self, employee_id: int, first_name: str, last_name: str, 
                     role: str, hourly_rate: float, role_coefficient: float = 1.0):
        """
        Добавляет сотрудника в таблицу.
        При повторном добавлении того же ID можно решить, что делать: 
        - Игнорировать (INSERT OR IGNORE) 
        - Перезаписать (INSERT OR REPLACE)
        - Выбросить ошибку.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Здесь используем INSERT OR IGNORE (или REPLACE) по желанию
            cursor.execute("""
                INSERT OR IGNORE INTO employees (
                    employee_id, first_name, last_name, role, hourly_rate, role_coefficient
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (employee_id, first_name, last_name, role, hourly_rate, role_coefficient))
            conn.commit()

    def get_employee(self, employee_id: int):
        """
        Возвращает информацию о сотруднике по ID (или None, если не найден).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
            row = cursor.fetchone()
            if row:
                # row — кортеж: (employee_id, first_name, last_name, role, hourly_rate, role_coefficient)
                return {
                    "employee_id": row[0],
                    "first_name": row[1],
                    "last_name": row[2],
                    "role": row[3],
                    "hourly_rate": row[4],
                    "role_coefficient": row[5]
                }
            else:
                return None

    def get_all_employees(self):
        """
        Возвращает список всех сотрудников (каждый в виде словаря).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM employees")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append({
                    "employee_id": row[0],
                    "first_name": row[1],
                    "last_name": row[2],
                    "role": row[3],
                    "hourly_rate": row[4],
                    "role_coefficient": row[5]
                })
            return result
