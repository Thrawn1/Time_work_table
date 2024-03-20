import sqlite3
from prettytable import PrettyTable

# Проверка заполнения таблиц
conn = sqlite3.connect('company.db')
cursor = conn.cursor()
cursor.execute('''SELECT employees.id, employees.first_name, 
               employees.last_name, roles.name, employees.hourly_rate, 
               employees.hire_date, employees.birth_date FROM employees 
               INNER JOIN roles ON employees.role = roles.id''')
rows = cursor.fetchall()

# Создаем объект PrettyTable и добавляем заголовки
table = PrettyTable()
table.field_names = ["ID сотрудника", "Имя", "Фамилия", "Роль", "Почасовая ставка", "Дата приема на работу", "Дата рождения"]

# Добавляем строки в таблицу
for row in rows:
    table.add_row(row)

# Выводим таблицу
print(table)
