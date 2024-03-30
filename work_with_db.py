from os.path import isfile
import sqlite3
from colorama import init, Fore, Style
from toml import load

def get_date_list_from_file(name_file:str) -> list:
    date_list = []
    with open(name_file, 'r') as file:
        for line in file:
            date_list.append(line.strip())
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

def check_data_label(name_file_data_label:str, name_db:str) -> bool:
    if isfile(name_file_data_label):
        pass
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

def load_data(name_db:str, name_file_toml_user_and_roles:str, 
name_file_data_label:str) -> None:
    if isfile(name_db):
        if check_data_toml(name_file_toml_user_and_roles):
            conn = sqlite3.connect(name_db)
            cursor = conn.cursor()
            with open(name_file_toml_user_and_roles, 'r') as file:
                data = load(file)
                for key, value in data.items():
                    cursor.execute("""INSERT INTO roles (name, description, 
                                   work_shift, lost_tag_flag) 
                                   VALUES (?, ?, ?, ?)""",
                                   (key, value['description'], 
                                    value['work_shift'], 
                                    value['lost_tag_flag']))
            conn.commit()
            conn.close()
        else:
            print(f"В файле '{name_file_toml_user_and_roles}' нет данных.")
    else:
        print(f"Ошибка: Файл '{name_db}' не найден.")
        create_db(name_db)
        print(f"Пустая база данных '{name_db}' создана.")
        load_data(name_db, name_file_toml_user_and_roles, name_file_data_label)
        