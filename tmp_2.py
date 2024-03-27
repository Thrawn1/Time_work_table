import re
import sqlite3  
import prettytable

name_db = 'line_new.db'

with open('2_attlog.dat', 'r') as file:
    rows = file.readlines()

def parse_rows(input_rows):
    parsed_rows = []
    for row in input_rows:
        # Разделяем строку по пробелам и табуляции
        parts = re.split(r'\s+', row)  # \s+ соответствует одному или 
        #более пробельным символам
        id_, date, time = parts[1], parts[2], parts[3]
        parsed_rows.append([int(id_), date, time])
    return parsed_rows

parsed_list = parse_rows(rows)

# Создаем базу данных SQLite
conn = sqlite3.connect(name_db)
cursor = conn.cursor()
# Создаем таблицу line в базе данных. Если таблица уже существует, то  
    # она не будет создана. Таблица содержит три столбца: id,id_user, date, time,
#create date, update flag, update date. При создании записи в таблице
# update_flag устанавливается в NULL и update_date устанавливается в NULL
cursor.execute('''CREATE TABLE IF NOT EXISTS line
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_user INTEGER,
                date TEXT,
                time TEXT,
                create_date TEXT DEFAULT CURRENT_TIMESTAMP,
                update_flag INTEGER DEFAULT NULL,
                update_date TEXT DEFAULT NULL)''')
conn.commit()
# Заполнение таблицы line данными из файла 2_attlog.dat

unique_dates = set([item[1] for item in parsed_list])
unique_dates_db = set()
cursor.execute('SELECT date FROM line')
for row in cursor.fetchall():
    unique_dates_db.add(row[0])

#print(unique_dates_db)

add_date = unique_dates - unique_dates_db
print(add_date)


for date in unique_dates.copy():
    cursor.execute('SELECT * FROM line WHERE date = ?', (date,))
    existing_row = cursor.fetchone()
    if existing_row is not None:
        unique_dates.remove(date)


for item in parsed_list:
    if item[1] in unique_dates:
        # Если записи с такой же датой нет, то создаем новую запись
        cursor.execute('INSERT INTO line (id_user, date, time) VALUES (?, ?, ?)',
                       (item[0], item[1], item[2]))

conn.commit()
# Запрос данных из таблицы line последних 20 записей и вывод их на экран
# cursor.execute('SELECT * FROM line ORDER BY id DESC LIMIT 20')
# print(cursor.fetchall())
# conn.close()
# Запрос данных из таблицы line за март 2020 года и вывод их на экран в красивом виде с помощью prettytable
cursor.execute('SELECT * FROM line WHERE date LIKE "2021-09%" ORDER BY date, id_user,time')
data = cursor.fetchall()
table = prettytable.PrettyTable()
table.field_names = ['id', 'id_user', 'date', 'time', 'create_date', 'update_flag', 'update_date']
for row in data:
    table.add_row(row)
print(table)

# Получить последний id
cursor.execute('SELECT MAX(id) FROM line')
print(cursor.fetchone()[0])

#Получить первую  дату за 2020 год для id=6
cursor.execute('SELECT date,time FROM line WHERE id_user = 6 AND date LIKE "2020%" ORDER BY date LIMIT 1')
print(cursor.fetchone())


conn.close()



