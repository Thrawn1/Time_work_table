import sqlite3
from toml import load
import os

def check_data_toml(name_file:str) -> bool:
    try:
        with open(name_file, 'r') as file:
            data = load(file)
            if len(data) == 0:
                return False
            return True
    except FileNotFoundError:
        print(f"Error: File '{name_file}' not found.")
        return False
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def check_data_label(name_file:str) -> bool:
    if os.path.exists(name_file):
        with open(name_file, 'r') as file:
            data = load(file)
            if len(data) == 0:
                return False
            return True
    return False

def check_db(name_db:str) -> bool:
    if os.path.exists(name_db):
        return True
    return False

def check_data_db(name_db:str) -> bool:
    if  check_db(name_db):
        conn = sqlite3.connect(name_db)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM employees')
        if len(cursor.fetchall()) == 0:
            return False
        return True
    else:
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

def load_data(name_db:str, name_file_toml_user_and_roles:str, name_file_data_label:str) -> None:
    with open(name_file_toml_user_and_roles, 'r', encoding='utf-8') as file:
        data = load(file)
    if check_data_toml(name_file_toml_user_and_roles):
        conn = sqlite3.connect(name_db)
        cursor = conn.cursor()
        for role in data['roles']:
            cursor.execute('''
            INSERT INTO roles (name, description, work_shift, lost_tag_flag)
            VALUES (?, ?, ?, ?)
            ''', (role['name'], role['description'], role['work_shift'], role['lost_tag_flag']))
        for employee in data['employees']:
            cursor.execute('''
            INSERT INTO employees (id, first_name, last_name, role, hourly_rate, hire_date, birth_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (employee['id'], employee['first_name'], employee['last_name'], employee['role'], employee['hourly_rate'], employee['hire_date'], employee['birth_date']))
        conn.commit()
        conn.close()    
