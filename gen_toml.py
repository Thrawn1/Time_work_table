body_toml = """
#Для загрузки данных раскоментируйте строки и заполните их данными

#[[employees]]
#  id = 0
#  first_name = 'Иван'
#  last_name = 'Михайлов'
#  role = 'Работник цеха'
#  hourly_rate = 82323
#  hire_date = '12.07.2017'
#  birth_date = '12.07.1967'

# [roles]
#   [roles.simple_role]
#   id = 0
#    name = 'Рабртник цеха'
#    description = 'Работник цеха'
#    work_shift = 8
#    lost_tag_flag = 1
"""

with open('company_data.toml', 'w', encoding='utf-8') as file:
    file.write(body_toml)