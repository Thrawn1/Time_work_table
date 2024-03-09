import sqlite3
import os
import toml



# Чтение TOML файла с указанием кодировки 'utf-8'
with open('company_data.toml', 'r', encoding='utf-8') as file:
    data = toml.load(file)


#Объекты:
#    - Работник:
#        - id
#        - Имя
#        - Фамилия
#        - Роль
#        - Ставка рабочего дня
#        - Дата приема на работу
#        - Дата рождения
#    - Роль:
#        - id
#        - Название
#        - Описание
#        - Длина рабочей смены
#        - Флаг утери тега

# Если файла БД не существует, то создаем его
if not os.path.exists('company.db'):
    # Создание базы данных
    conn = sqlite3.connect('company.db')
    conn.close()
# Если в БД нет таблицы employees или roles, то создаем их
conn = sqlite3.connect('company.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT,
        last_name TEXT,
        role TEXT,
        hourly_rate INTEGER,
        hire_date TEXT,
        birth_date TEXT
    )
''')
conn.commit()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        work_shift INTEGER,
        lost_tag_flag INTEGER
    )
''')

conn.commit()

# Если в файле TOML есть данные, то заполняем таблицы
if len(data) != 0:
    # Заполнение таблицы employees
    for employee in data['employees']:
        cursor.execute('''
            INSERT INTO employees (first_name, last_name, role, hourly_rate, hire_date, birth_date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (employee['first_name'], employee['last_name'], employee['role'],
               employee['hourly_rate'], employee['hire_date'], employee['birth_date']))
        conn.commit()
    # Заполнение таблицы roles
    for role_s in data['roles']:
            cursor.execute('''
                           INSERT INTO roles (name, description, work_shift, lost_tag_flag)
                           VALUES (?, ?, ?, ?)
                    ''', (data['roles'][role_s]['name'], data['roles'][role_s]['description'], 
                          data['roles'][role_s]['work_shift'], 
                          data['roles'][role_s]['lost_tag_flag']))
            conn.commit()

#Закрыть соединение
conn.close()