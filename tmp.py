import sqlite3
new_file = '2_attlog.dat'

data_list = []

with open ('1_attlog.dat', 'r') as file:
    for line in file:
        line_3 = line.strip()
        print(len(line_3[1][0]))
        now_year = int(line[10:14])
        if 2015 < now_year:
            data_list.append(line)
        else:
            pass
#            print(line)

with open(new_file, 'w') as file:
    for line in data_list:
        file.write(line)


name_db = 'line.db'
conn = sqlite3.connect(name_db)
cursor = conn.cursor()
# Создание таблицы line в базе данных. Если таблица уже существует, то
# она не будет создана
cursor.execute('''CREATE TABLE IF NOT EXISTS line
                (id INTEGER PRIMARY KEY AUTOINCREMENT,
                line TEXT)''')
conn.commit()
# Заполнение таблицы line данными из файла 2_attlog.dat
with open(new_file, 'r') as file:
    for line in file:
        cursor.execute('INSERT INTO line (line) VALUES (?)', (line,))
conn.commit()

# Запрос данных из таблицы line
cursor.execute('SELECT * FROM line')
#print(cursor.fetchall())
conn.close()
