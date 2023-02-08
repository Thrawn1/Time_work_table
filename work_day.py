from lable import Lable
from datetime import time
class Work_day():
    """Данный класс хранит информацию за день. Атрибутами являются год,месяц,день в числовом виде, а так же день недели, название месяца в строковом виде
     метка прихода, метка ухода """

    year = None
    month = None
    day = None
    day_of_week = None
    month_name = None
    lable_come = None
    lable_go = None
    
    def __init__(self, lable_first:Lable):
        months_name = ('Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь')
        names_weekdays = ('Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье')
        self.year = lable_first.get_date().year
        self.month = lable_first.get_date().month
        self.month_name = months_name[int(lable_first.get_date().month) - 1]
        self.day = lable_first.get_date().day
        self.day_of_week = names_weekdays[lable_first.get_date().weekday()]
        self.lable_come = lable_first
        self.lable_go = lable_first
    
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
        return self.lable_come
    
    def get_go(self):
        """Данный метод возвращает метку ухода"""
        return self.lable_go

    def define_loss_lable(self):
        """Данный метод определяет, есть ли потерянная метка"""
        if self.lable_come.get_flag() == self.lable_go.get_flag():
            return True
        else:
            return False
    def __str__(self) -> str:
        number_char = len(self.day_of_week)
        if number_char < 11:
            self.day_of_week = self.day_of_week + ' '*(11 - number_char)
        return f'{self.day} {self.month_name} {self.year} - {self.day_of_week}'
    
    def edit_lable(self, flag):
        """Данный метод редактирует метку. В качестве аргумента принимает флаг, который определяет, какую метку редактировать"""
        new_time_row = input('Введите время метки в формате ЧЧ ММ СС: ')
        list_data = new_time_row.split(' ')
        new_time = list_data[0] + ':' + list_data[1] + ':' + list_data[2]
        #new_time = '12:12:12'
        #Имеет смысл переработать старые функции, что бы они проверяли корректность ввода и добавляли недостающие данные по рандому
        if flag == 0 or time.fromisoformat(new_time) < self.lable_go:
           self.lable_come.edit_lable(new_time)
        elif flag == 1:
           self.lable_go.edit_time_lable(new_time)
        else:
            print('Ошибка определения редактируемой метки')