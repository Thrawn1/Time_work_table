import toml


# Чтение TOML файла с указанием кодировки 'utf-8'
with open('company_data.toml', 'r', encoding='utf-8') as file:
    data = toml.load(file)

# Проверка, пустые ли поля
print(data)
print(type(data))
print (data.values())

if len(data) == 0:
    print('Файл пуст')
else:
    print('Файл не пуст')