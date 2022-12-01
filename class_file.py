from datetime import date,time
from datetime import time
from random import randint
from os import path


class read_file_row_data():
    """Данный метод необходим, что бы открыть файл с датчика, прочитать данные и сформировать список с данными за месяц. 
    Данные об отметке хранятся как строка.Данный объект хранит имя файла с данными и путь к файлу."""
    def __init__(self):
        self.file_name = '1_attlog.dat'
        self.directory = 'data' 
        self.file_data = []
        self.requset_year = 0
        self.requset_month = 0
    def search_work_period(self):
        """Данный метод ищет в файле данные за определенный месяц и год. Данные хранятся в списке file_data"""
        with open(path.join(self.directory,self.file_name)) as file:
            for line in file:
                if self.detect_data(line[10:17]):
                    self.file_data.append(line)
    def detect_data(self,row_date:str):
        """Данный метод ищет в списке file_data данные за определенный месяц и год. Данные хранятся в списке file_data"""
        row_year = int(row_date[0:4])
        row_month = int(row_date[5:])
        if row_year == self.requset_year and row_month == self.requset_month:
            return True




class lable():
    """Данный класс описывает объект, который хранит в себе информацию о метке с датчика. В качестве атрибутов 
    класса используются дата, время, флаг, который определяет тип метки(приход или уход), а также строка из файла с датчика,
     по которой строится объект класса """
    
    row_data = '' # Переменная для хранения строки из файла
    flag = 3 # Переменная для хранения флага. Если 0 - приход, если 1 - уход, 3 - значение по умолчанию, требуется проверка
    date = None # Переменная для хранения даты метки
    time = None # Переменная для хранения времени метки 
    
    def __init__(self, row_data):
        """Данный метод инициализирует объект класса"""
        self.row_data = row_data
        self.date = date.fromisoformat(row_data[10:20]) #Берем срез строки, в котооых хранится дата, создаем объект класса date
        self.time =  time.fromisoformat(row_data[21:29]) #Берем срез строки, в котором хранится время, создаем объект класса time
        self.flag = 3 
   
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
    def get_day(self):
        """Данный метод возвращает значение дня"""
        return self.date.day
   
    def random_time_set(self,hour_second_label:int,flag_second_label:int):
        if flag_second_label == 0:
            hour = randint(hour_second_label,21)
        elif flag_second_label == 1:
            hour = randint(5,hour_second_label)
        minute = randint(0,59)
        second = randint(0,59)
        self.time = time(hour,minute,second)

    def edit_time_lable(self,edit_time:str):
        """Данный метод изменяет время метки на заданное значение"""
        self.time = time.fromisoformat(edit_time)
   
    def __str__(self) -> str:
        """Данный метод возвращает строковое представление объекта класса"""
        if self.flag == 0:
            flag_str = 'Приход'
        elif self.flag == 1:
            flag_str = 'Уход'
        else:
            flag_str = 'Не определен'
        return f'flag: {flag_str}, date: {self.date}, time: {self.time}'



class work_day():
    """Данный класс хранит информацию за день. Атрибутами являются год,месяц,день в числовом виде, а так же день недели, название месяца в строковом виде
     метка прихода, метка ухода """
    year = None
    month = None
    day = None
    day_of_week = None
    month_name = None
    lable_come = None
    lable_go = None
    
    def __init__(self, lable_first:lable):
        months_name = ('Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь')
        names_weekdays = ('Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье')
        self.year = lable_first.get_date().year
        self.month = lable_first.get_date().month
        self.month_name = months_name[int(lable_first.get_date().month) - 1]
        self.day = lable_first.get_date().day
        self.day_of_week = names_weekdays[lable_first.get_date().weekday()]
        self.come = lable_first
        self.go = lable_first
    
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

    def define_loss_lable(self):
        """Данный метод определяет, есть ли потерянная метка"""
        if self.come.get_flag() == self.go.get_flag():
            return True
        else:
            return False
     

class work_month():
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
    
    def build_day_object(self):
        """Данный метод создает объекты класса day"""
        for line in self.month_data_raw:
            id_row = int(line[7:10])
            if id_row not in self.work_employees:
                self.work_employees[id_row] = employee(id_row)
            obj_lable = lable(line)
            flag_chek_day = self.check_day_in_list_month(id_row, obj_lable.get_day())
            if flag_chek_day == False:
                obj_day = work_day(obj_lable)
                self.month_data[id_row] = obj_day
            else:
                self.month_data[id_row].
                pass    
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
    def check_day_in_list_month(self,id:int,day:int):
        """Данный метод проверяет, есть ли день в списке дней месяца"""
        if day in self.month_data[id]:
            return True
        else:
            return False

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