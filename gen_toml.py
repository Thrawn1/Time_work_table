body_toml = """
#Для загрузки данных раскоментируйте строки и заполните их данными



# [roles]

# [roles.simple_role0]
# id = 100
# name = 'Название роли'
# description = 'Описание роли'
# work_shift = 24
# lost_tag_flag = 3

# [roles.simple_role1]
# id = 101
# name = 'Название роли'
# description = 'Описание роли'
# work_shift = 8
# lost_tag_flag = 4


# [[employees]]
# id = 100
# first_name = 'Иван'
# last_name = 'Иванов'
# role = 'Кто то'
# hourly_rate = 0
# hire_date = '00.00.0000'
# birth_date = '00.00.0000'

# [[employees]]
# id = 101
# first_name = 'Петр'
# last_name = 'Петров'
# role = 'Еще кто то там'
# hourly_rate = 0
# hire_date = '00.00.0000'
# birth_date = '00.00.0000'


"""

with open('company_data.toml', 'w', encoding='utf-8') as file:
    file.write(body_toml)