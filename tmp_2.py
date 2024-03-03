import toml
# Создание словаря с данными
data = {
    'employees': [
        {
            'id': '',
            'name': '',
            'surname': '',
            'role': '',
            'rate': '',
            'start_date': ''
        }
    ]
}

# Запись данных в TOML файл
with open('data/empty_file.toml', 'w') as file:
    file.write("# This is a comment\n")
    toml.dump(data, file)