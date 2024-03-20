import sqlite3
import os
import toml
import datetime



def convert_to_iso(date):
    try:
        date_obj = datetime.datetime.strptime(date, '%d.%m.%y')
        iso_date = date_obj.date().isoformat()
        return iso_date
    except ValueError:
        print("Неверный формат даты. Пожалуйста, укажите дату в формате ДД.ММ.ГГ.")


def convert_to_ddmmyy(date):
     try:
        date_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
        ddmmyy_date = date_obj.strftime('%d.%m.%y')
        return ddmmyy_date
     except ValueError:
        print("Неверный формат даты. Пожалуйста, укажите дату в формате ГГГГ-ММ-ДД.")



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
        id INTEGER,
        first_name TEXT,
        last_name TEXT,
        role TEXT,
        hourly_rate INTEGER,
        hire_date TEXT,
        birth_date TEXT,
        FOREIGN KEY (role) REFERENCES roles(name)
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
    # Заполнение таблицы roles
    if 'roles' in data:
        for role_s in data['roles']:
            cursor.execute('SELECT name FROM roles WHERE name = ?', (data['roles'][role_s]['name'],))
            existing_role = cursor.fetchone()
            if existing_role is None:
                cursor.execute('''
                    INSERT INTO roles (name, description, work_shift, lost_tag_flag)
                    VALUES (?, ?, ?, ?)
                ''', (data['roles'][role_s]['name'], data['roles'][role_s]['description'],
                      data['roles'][role_s]['work_shift'], data['roles'][role_s]['lost_tag_flag']))
                conn.commit()
                print('Коммит прошел успешно')
            else:
                print(f"Role with name {data['roles'][role_s]['name']} already exists")

    # Заполнение таблицы employees
    if 'employees' in data:
        for employee in data['employees']:
            # Проверка наличия записи с таким id
            cursor.execute('SELECT id FROM employees WHERE id = ?', (employee['id'],))
            existing_employee = cursor.fetchone()
            if existing_employee is None:
                cursor.execute('SELECT id FROM roles WHERE name = ?', (employee['role'],))
                existing_role = cursor.fetchone()
                if existing_role is None:
                    print(f"Role '{employee['role']}' does not exist")
                else:
                    cursor.execute('''
                        INSERT INTO employees (id, first_name, last_name, role, hourly_rate, hire_date, birth_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (employee['id'], employee['first_name'], employee['last_name'], existing_role[0],
                          employee['hourly_rate'], employee['hire_date'], employee['birth_date']))
                    conn.commit()
            else:
                print(f"Employee with id {employee['id']} already exists")

#Закрыть соединение
conn.close()

# Проверка заполнения таблиц
conn = sqlite3.connect('company.db')
cursor = conn.cursor()
cursor.execute('''SELECT employees.id, employees.first_name, 
               employees.last_name, roles.name, employees.hourly_rate, 
               employees.hire_date, employees.birth_date FROM employees 
               INNER JOIN roles ON employees.role = roles.id''')
rows = cursor.fetchall()
for row in rows:
    employee_id, first_name, last_name, role_name, hourly_rate, hire_date, birth_date = row
    print((
        f"ID сотрудника: {employee_id}, "
        f"Имя: {first_name}, "
        f"Фамилия: {last_name}, "
        f"Роль: {role_name}, "
        f"Почасовая ставка: {hourly_rate}, "
        f"Дата приема на работу: {hire_date}, "
        f"Дата рождения: {birth_date}"
    ))

cursor.execute('''SELECT roles.id, roles.name, roles.description, 
               roles.work_shift, roles.lost_tag_flag FROM roles''')
rows = cursor.fetchall()
for row in rows:
    role_id, role_name, role_description, work_shift, lost_tag_flag = row
    print((
        f"ID роли: {role_id}, "
        f"Название: {role_name}, "
        f"Описание: {role_description}, "
        f"Длина рабочей смены: {work_shift}, "
        f"Флаг утери тега: {lost_tag_flag}"
    ))

print("""------------------------------------------------------------------
      ---------------------------------------------------------------------""")
conn.close()

# Проверка наличия файла БД
print(os.path.exists('company.db'))
# Удаление файла toml
os.remove('company_data.toml')
#Создание файла toml c помощью gen_toml.py
os.system('python gen_toml.py')
# Проверка наличия файла toml
print(os.path.exists('company_data.toml'))