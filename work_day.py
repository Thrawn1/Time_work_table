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
    
