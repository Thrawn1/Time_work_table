from datetime import datetime
from datetime import time as dt_time
from random import randint
class lable():
    """Данный класс описывает объект, который хранит в себе как атрибут главный флаг - если метка прихода 0, если уход 1. 
    Кроме того в качестве атрибута хранится строковое значение даты и времени """
    row_data = '' # Переменная для хранения строки из файла
    flag = 0 # Переменная для хранения флага. Если 0 - приход, если 1 - уход
    date = None # Переменная для хранения даты метки
    time = None # Переменная для хранения времени метки 
    
    def __init__(self, row_data):
        """Данный метод инициализирует объект класса"""
        self.row_data = row_data
        self.date = row_data[1:17] #Берем срез строки, в котором хранится дата, создаем объект класса datetime и сохраняем в атрибут
        self.time = row_data[18:24] #Берем срез строки, в котором хранится время, создаем объект класса datetime и сохраняем в атрибут
    def set_flag(self, value):
        """Данный метод устанавливает значение флага"""
        self.flag = value
    def get_flag(self):
        """Данный метод возвращает значение флага"""
        return self.flag
    def get_date(self):
        """Данный метод возвращает значение даты"""
        return self.date
    def get_time(self):
        """Данный метод возвращает значение времени"""
        return self.time
    def random_time_set(self):
        pass
 



class read_file_row_data():
    """Данный метод необходим, что бы открыть файл с датчика, прочитать данные и сформировать список с данными за месяц. Данные об отметке хранятся как объект класса lable 
    Данный объект хранит в себе год и месяц, за которые нужны данные. Данный объект хранит имя файла с данными и путь к файлу."""
    def __init__(self, lable):
        self.lable = lable
        self.file_name = lable.file_name
        self.file_path = lable.file_path
        self.file_data = []
        self.file_data = self.read_file_data()
    def read_file_data(self):
        """Данный метод открывает файл с датчика, читает данные и возвращает список с данными за месяц"""
        file_data = []
        with open(self.file_path + self.file_name, 'r') as file:
            for line in file:
                file_data.append(line)
        return file_data
    def get_file_data(self):
        """Данный метод возвращает список с данными за месяц"""
        return self.file_data


class day():
    """Данный класс хранит информацию за день. Атрибутами являются год,месяц,день в числовом виде, а так же день недели, название месяца в строковом виде
     метка прихода, метка ухода """
    def __init__(self, year, month, day, day_of_week, month_name, come, go):
        self.year = year
        self.month = month
        self.day = day
        self.day_of_week = day_of_week
        self.month_name = month_name
        self.come = come
        self.go = go
    def get_year(self):
        """Данный метод возвращает год"""
        return self.year
    def get_month(self):
        """Данный метод возвращает месяц"""
        return self.month
    def get_day(self):
        """Данный метод возвращает день"""
        return self.day
    def get_day_of_week(self):
        """Данный метод возвращает день недели"""
        return self.day_of_week
    def get_month_name(self):
        """Данный метод возвращает название месяца"""
        return self.month_name
    def get_come(self):
        """Данный метод возвращает метку прихода"""
        return self.come
    def get_go(self):
        """Данный метод возвращает метку ухода"""
        return self.go

class month():
    """Данный класс хранит информацию за месяц. Атрибутами являются год,месяц, название месяца в строковом виде, словарь работников, ключи словаря - это if работников, значенеие
    - это список с объектами класса employee, словарь с данными за месяц, где ключом является id работника, а значением объект с данными за день"""
    def __init__(self, year, month, month_name, employees, month_data):
        self.year = year
        self.month = month
        self.month_name = month_name
        self.employees = employees
        self.month_data = month_data
    def get_year(self):
        """Данный метод возвращает год"""
        return self.year
    def get_month(self):
        """Данный метод возвращает месяц"""
        return self.month
    def get_month_name(self):
        """Данный метод возвращает название месяца"""
        return self.month_name
    def get_employees(self):
        """Данный метод возвращает словарь работников"""
        return self.employees
    def get_month_data(self):
        """Данный метод возвращает словарь с данными за месяц"""
        return self.month_data
class employee():
    """Данный класс хранит информацию о работнике. Атрибутами являются id работника, фамилия, имя,
    зарплатная ставка,роль, общее рабочее время за месяц"""
    def __init__(self, id, surname, name, rate, role, total_work_time):
        self.id = id
        self.surname = surname
        self.name = name
        self.rate = rate
        self.role = role
        self.total_work_time = total_work_time
    def get_id(self):
        """Данный метод возвращает id работника"""
        return self.id
    def get_surname(self):
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
class excel_table():
    """Данный класс хранит информацию для построения таблицы в excel,имя файла, путь до файла. Имеет метод построения excel файла"""
    pass
class html_file():
    """Данный класс хранит информацию для построения html файла, имя файла, путь до файла. Имеет метод построения html файла"""
    pass