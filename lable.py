from random import randint
from datetime import date,time

class Lable():
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
        self.flag = 0 
   
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