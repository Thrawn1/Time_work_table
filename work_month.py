from work_day import Work_day
from lable import Lable
from employee import Employee
from calendar import monthrange
from datetime import date
from os.path import join

class Work_month():
    """Данный класс хранит информацию за месяц. 
    Атрибутами являются год,месяц, название месяца в строковом виде, словарь работников, 
    ключи словаря - это id работников, значенеие - это список с объектами класса employee, 
    словарь с данными за месяц, где ключом является id работника, а значением объект с данными за день"""
    def __init__(self, year:int, month:int,month_data:list):
        months_name = ('Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь')
        self.year = year
        self.month = month
        self.month_name = months_name[month - 1]
        self.work_employees = {}
        self.month_data_raw = month_data
        self.month_data = {}
        self.loss_lable_days = {}
        self.loss_all_data_days = {}
    
