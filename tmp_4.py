from os.path import isfile
import sqlite3
import re
from colorama import init, Fore, Style
from toml import load

def screening_row(screen_condition:set,name_file_data_label:str) -> list:
    rows = []
    with open(name_file_data_label, 'r') as file:
        all_lines = file.readlines()
    for condition in screen_condition:
        year = condition[:4]
        month = condition[5:]
        for line in all_lines:
            parts = re.split(r'\s+', line)
            if parts[2][:7] == year + '-' + month:
                rows.append(line)
    return rows
def get_date_list_from_file(name_file:str) -> set:
    """
    Получает список дат из файла.

    Аргументы:
    name_file (str): Путь к файлу.

    Возвращает:
    set: Множество уникальных дат в формате 'YYYY-MM'.

    Пример использования:
    >>> get_date_list_from_file('/path/to/file.txt')
    {'2022-01', '2022-02', '2022-03'}
    """
    date_list = set()
    with open(name_file, 'r') as file:
        rows = file.readlines()
    for row in rows:
        parts = re.split(r'\s+', row)
        if int(parts[2][:4]) > 2015:
            date = parts[2][:7]
            date_list.add(date)
    return date_list
def get_date_list_from_db(name_db:str) -> set:
    """
    Получает список дат из базы данных.

    Аргументы:
    name_db (str): Путь к файлу базы данных.

    Возвращает:
    set: Множество уникальных дат в формате "гггг-мм".
    """
    conn = sqlite3.connect(name_db)
    cursor = conn.cursor()
    cursor.execute('SELECT date FROM line')
    date_list = set()
    for row in cursor.fetchall():
        date_list.add(row[0][:7])
    return date_list
def generate_toml(name_file:str) -> None:
    pass

def check_data_toml(name_file:str) -> bool:
    if isfile(name_file):
        with open(name_file, 'r') as file:
            data = load(file)
            if len(data) == 0:
                return False
            return True
    else:
        generate_toml(name_file)
        print(f"Файл '{name_file}' не найден. Создан новый дефолтный файл.")
        return False
def get_diff_data(name_file_data_label:str, name_db:str) -> set:
    data_from_file = get_date_list_from_file(name_file_data_label)
    data_from_db = get_date_list_from_db(name_db)
    difference_data = data_from_file - data_from_db
    return difference_data
def check_data_label(name_file_data_label:str, name_db:str) -> bool:
    if isfile(name_file_data_label):
        difference_data = get_diff_data(name_file_data_label, name_db)
        if len(difference_data) > 0:
            return True
        else:
            print (Fore.GREEN + Style.BRIGHT +
                   f"Новых данных в '{name_file_data_label}' нет.")
            return False
    else:
        init(autoreset=True)  # Инициализация модуля colorama
        print(Fore.RED + Style.BRIGHT+
              f"Ошибка: Файл '{name_file_data_label}' с датчика отсутствует.")
        return False
def create_db(name_db:str) -> None:
    conn = sqlite3.connect(name_db)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        work_shift INTEGER,
        lost_tag_flag INTEGER
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        role TEXT,
        hourly_rate INTEGER,
        hire_date TEXT,
        birth_date TEXT,
        FOREIGN KEY (role) REFERENCES roles(name)
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS line (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_user INTEGER,
        date TEXT,
        time TEXT,
        create_date TEXT DEFAULT CURRENT_TIMESTAMP,
        update_flag INTEGER DEFAULT NULL,
        update_date TEXT DEFAULT NULL,
        FOREIGN KEY (id_user) REFERENCES employees(id)
    )
    ''')
    conn.commit()
    conn.close()
def insert_data_to_db(cursor:sqlite3.Cursor, data:dict, table:str) -> None:
    if table == 'roles':
        cursor.execute("""INSERT INTO roles (
                        name,
                        description,
                        work_shift,
                        lost_tag_flag)
                        VALUES (?, ?, ?, ?)""",
                        (data['name'], data['description'],
                        data['work_shift'], data['lost_tag_flag']))
    elif table == 'employees':
        cursor.execute("""INSERT INTO employees (
                        id,
                        first_name,
                        last_name,
                        role,
                        hourly_rate,
                        hire_date,
                        birth_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (data['id'], data['first_name'],
                        data['last_name'], data['role'],
                        data['hourly_rate'], data['hire_date'],
                        data['birth_date']))
    elif table == 'line':
        cursor.execute("""INSERT INTO line (id_user, date, time)
                           VALUES (?, ?, ?)""", (data['id_user'], data['date'],
                           data['time']))
def update_data_to_db(cursor:sqlite3.Cursor, data:dict, table:str) -> None:
    if table == 'roles':
        cursor.execute("""UPDATE roles SET
                        name = ?,
                        description = ?,
                        work_shift = ?,
                        lost_tag_flag = ?
                        WHERE id = ?""",
                        (data['name'], data['description'],
                        data['work_shift'], data['lost_tag_flag'],
                        data['id']))
    elif table == 'employees':
        cursor.execute("""UPDATE employees SET
                        first_name = ?,
                        last_name = ?,
                        role = ?,
                        hourly_rate = ?,
                        hire_date = ?,
                        birth_date = ?
                        WHERE id = ?""",
                        (data['first_name'], data['last_name'],
                        data['role'], data['hourly_rate'],
                        data['hire_date'], data['birth_date'],
                        data['id']))
    elif table == 'line':
        cursor.execute("""UPDATE line SET
                id_user = ?,
                date = ?,
                time = ?,
                update_flag = 1,
                update_date = CURRENT_TIMESTAMP
                WHERE id = ?""",
                (data['id_user'], data['date'], data['time'],
                data['id']))
def load_data(name_db:str, name_file_toml_user_and_roles:str,
name_file_data_label:str) -> None:
    if isfile(name_db):
        if check_data_toml(name_file_toml_user_and_roles):
            conn = sqlite3.connect(name_db)
            cursor = conn.cursor()
            with open(name_file_toml_user_and_roles, 'r') as file:
                data = load(file)
            for role in data['roles']:
                if 'id' not in role.keys():
                    insert_data_to_db(cursor, role, 'roles')
                else:
                    update_data_to_db(cursor, role, 'roles')
            for employee in data['employees']:
                if 'id' not in employee.keys():
                    insert_data_to_db(cursor, employee, 'employees')
                else:
                    update_data_to_db(cursor, employee, 'employees')
        else:
            print(f"В файле '{name_file_toml_user_and_roles}' нет данных.")
        if check_data_label(name_file_data_label, name_db):
            diff_year_and_months = get_diff_data(name_file_data_label, name_db)
            rows = screening_row(diff_year_and_months, name_file_data_label)
            conn = sqlite3.connect(name_db)
            cursor = conn.cursor()
            for row in rows:
                parts = re.split(r'\s+', row)
                data = {
                    'id_user': parts[1],
                    'date': parts[2],
                    'time': parts[3]
                }
                insert_data_to_db(cursor, data, 'line')
        else:
            print(f"В файле '{name_file_data_label}' нет новых данных.")
        conn.commit()
        conn.close()
    else:
        print(f"Ошибка: Файл '{name_db}' не найден.")
        create_db(name_db)
        print(f"Пустая база данных '{name_db}' создана.")
        load_data(name_db, name_file_toml_user_and_roles, name_file_data_label)