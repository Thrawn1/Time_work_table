from os import path

class Employee():
    """Данный класс хранит информацию о работнике. Атрибутами являются id работника, фамилия, имя,
    зарплатная ставка,роль, общее рабочее время за месяц"""

    id = None
    family = ''
    name = ''
    rate = 0
    role = ''

    def __init__(self, id):
        directory_name_1 = 'data'
        directory_name_2 = 'variable_data_for_app'
        str_name_file = 'id_employee.dat'
        str_rate_file = 'wage_rates.dat'
        str_role_file = 'roles_employee.dat'
        with open(path.join(directory_name_1,directory_name_2,str_name_file),'r',encoding='utf-8') as file:
            for line in file:
                line = line.rstrip('\n')
                line_data = line.split(' ')
                if int(line_data[0]) == id:
                    self.id = id
                    self.role = int(line_data[1].lstrip('[').rstrip(']'))
                    self.family = line_data[2]
                    self.name = line_data[3]
        with open(path.join(directory_name_1,directory_name_2,str_role_file), 'r',encoding='utf-8') as file:
            for line in file:
                line = line.rstrip('\n')
                line_data = line.split(' ')
                role_id = int(line_data[0].lstrip('[').rstrip(']'))
                if role_id == self.role:
                    self.role_name = line_data[1]
        with open(path.join(directory_name_1,directory_name_2,str_rate_file), 'r',encoding='utf-8') as file:
            for line in file:
                line = line.rstrip('\n')
                line_data = line.split(' ')
                data_rate = line_data[1].lstrip('[').rstrip(']')
                if int(line_data[0]) == self.id:
                    self.rate = data_rate
        self.total_work_time = 0
    def get_id(self):
        """Данный метод возвращает id работника"""
        return self.id
    def get_family(self):
        """Данный метод возвращает фамилию работника"""
        return self.surname
    def get_name(self):
        """Данный метод возвращает имя работника"""
        return self.name
    def get_rate(self):
        """Данный метод возвращает зарплатную ставку работника"""
        return self.rate
    def get_role(self):
        """Данный метод возвращает роль работника"""
        return self.role
    def get_total_work_time(self):
        """Данный метод возвращает общее рабочее время работника"""
        return self.total_work_time
    def info(self,f = 's'):
        """Данный метод выводит информацию о работнике"""
        if f == 's':
            if self.name == self.family:
                return(f'{self.name}')
            else:
                return(f'{self.family} {self.name}')
        elif f == 'f':
            return(f'Работник: {self.family} {self.name}. Роль: {self.role_name}. Зарплатная ставка: {self.rate}.')
    def __str__(self) -> str:
        """Данный метод возвращает строку с данными о работнике"""
        string = f'Работник: {self.family} {self.name}. Роль: {self.role_name}. Зарплатная ставка: {self.rate}.'
        return string