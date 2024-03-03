import toml
import sqlite3
import os
import shutil

# Чтение TOML файла
with open('data/your_file.toml', 'r') as file:
    data = toml.load(file)

# Проверка, пустые ли поля
if all(value for value in data.values()):
    # Создание соединения с базой данных
    conn = sqlite3.connect('your_database.db')
    c = conn.cursor()

    # Создание таблицы, если она еще не существует
    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT,
            surname TEXT,
            role TEXT,
            rate REAL,
            start_date TEXT
        )
    ''')

    # Вставка данных в таблицу
    for employee in data['employees']:
        c.execute('''
            INSERT INTO employees (id, name, surname, role, rate, start_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (employee['id'], employee['name'], employee['surname'], employee['role'], employee['rate'], employee['start_date']))

    # Закрытие соединения с базой данных
    conn.commit()
    conn.close()

    # Замена исходного TOML файла на новый TOML файл, где все поля пустые
    os.remove('data/your_file.toml')
    shutil.copy('data/empty_file.toml', 'data/your_file.toml')