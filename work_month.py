from work_day import Work_day
from lable import Lable
from employee import Employee

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
        self.loss_lable_days = []
        self.loss_all_data_days = []
    
    def build_day_object(self):
        """Данный метод создает объекты класса day"""
        for line in self.month_data_raw:
            id_row = int(line[7:10])
            if id_row not in self.work_employees:
                self.work_employees[id_row] = Employee(id_row)
            obj_lable = Lable(line)
            flag_chek_day = self.check_day_in_list_month(id_row, obj_lable.get_day())
            if flag_chek_day == False:
                obj_day = Work_day(obj_lable)
                self.month_data[id_row] = []
                self.month_data[id_row].append(obj_day)
            else:
                for day in self.month_data[id_row]:
                    if day.get_day() == obj_lable.get_day():
                        row_label = obj_lable.time
                        start_label = day.lable_come.time
                        end_label = day.lable_go.time
                        if row_label < start_label and row_label < end_label:
                            obj_lable.set_flag(0)
                            day.lable_come = obj_lable
                        elif row_label > start_label and row_label > end_label:
                            obj_lable.set_flag(1)
                            day.lable_go = obj_lable
                        elif row_label > start_label and row_label < end_label:
                            pass
                        else:
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
        return self.work_employees
    
    def get_month_data(self):
        """Данный метод возвращает словарь с данными за месяц"""
        return self.month_data
    
    def check_day_in_list_month(self,id:int,day:int):
        """Данный метод проверяет, есть ли день в списке рабочих  дней месяца для пользователя"""
        days_int_list = []
        if id in self.month_data.keys():
            for day_obj in self.month_data[id]:
                days_int_list.append(day_obj.get_day())
            if day in days_int_list:
                return True
            else:
                return False
        else:
            return False
    def check_loss_lable(self):
        """Данный метод проверяет, есть ли пропущенные метки за месяц"""
        for id in self.month_data:
            loss_lable_days = []
            for day in self.month_data[id]:
                if day.lable_come.flag == day.lable_go.flag:
                    loss_lable_days.append(day.get_day())
            self.loss_lable_days = loss_lable_days 
                
    def __str__(self) -> str:
        """Данный метод возвращает строку с данными за месяц"""
        work_employees = ' '
        for id in self.work_employees:
            work_employees += self.work_employees[id].info() + ', '
        work_employees = work_employees[:-2]
        string = f' Месяц: {self.month_name} {self.year} года.\n Работники: {work_employees}.\n Данные за месяц: {self.month_data}'
        return string