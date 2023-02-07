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
            self.loss_lable_days[id] = loss_lable_days
                
    def display_info_loss_lable(self):
        """Данный метод выводит информацию о пропущенных метках"""
        for id in self.loss_lable_days:
            if len(self.loss_lable_days[id]) != 0:
                print(f'Работник {self.work_employees[id].get_name()} {self.work_employees[id].get_surname()} пропустил метки в дни: {self.loss_lable_days[id]}')

    def _get_all_work_days_months_ideally(self):
        """Данный метод возвращает список со всеми рабочими днями месяца,учитывая все исключения и особенности произодственного календаря"""
        name_file_holiday = 'holidays.dat'
        name_file_postponed_works_days = 'postponed_working_days.dat'
        directory_1 = 'data'
        directory_2 = 'variable_data_for_app'
        path_file_holiday = join(directory_1,directory_2,name_file_holiday)
        path_file_postponed_works_days = join(directory_1,directory_2,name_file_postponed_works_days)
        list_obj_holiday = []
        list_obj_postponed_works_days = []
        all_work_days_months_ideally = []
        with open(path_file_holiday,'r',encoding='utf-8') as file:
            for line in file:
                line = line.rstrip('\n')
                str_line = line.split('.')
                srt_line_1 = [int(i) for i in str_line]
                if line[1] == self.month:
                    list_obj_holiday.append(srt_line_1[0])
                print(list_obj_holiday)
        with open(path_file_postponed_works_days,'r',encoding='utf-8') as file:
            for line in file:
                line = line.rstrip('\n')
                str_line = line.split('.')
                srt_line_1 = [int(i) for i in str_line]
                if line[1] == self.month:
                    list_obj_postponed_works_days.append(srt_line_1[0])
                print(list_obj_postponed_works_days)
        last_day_month = monthrange(self.year,self.month)[1]
        for i in range (1,last_day_month+1):
            date_obj = date(self.year,self.month,i)
            if date_obj.weekday() != 5 and date_obj.weekday() != 6:
                if i not in list_obj_holiday:
                    all_work_days_months_ideally.append(i)
            if len(list_obj_postponed_works_days) != 0:
                all_work_days_months_ideally += list_obj_postponed_works_days
                all_work_days_months_ideally = all_work_days_months_ideally.sort()
        return all_work_days_months_ideally

    def get_all_work_days_month(self):
        """Данный метод возвращает список с всеми рабочими днями месяца, учитывающий все 
        исключени и особенности произодственного календаря"""
        pass

    def check_loss_days_in_work_month(self):
        """Данный метод проверяет, есть ли пропущенные дни в месяце"""
        for id in self.month_data:
            loss_days = []
            for day in self.month_data[id]:
                if day.lable_come.flag == 1 or day.lable_go.flag == 0:
                    loss_days.append(day.get_day())
            self.loss_days_in_work_month[id] = loss_days

    def __str__(self) -> str:
        """Данный метод возвращает строку с данными за месяц"""
        work_employees = ' '
        for id in self.work_employees:
            work_employees += self.work_employees[id].info() + ', '
        work_employees = work_employees[:-2]
        string = f' Месяц: {self.month_name} {self.year} года.\n Работники: {work_employees}.\n Данные за месяц: {self.month_data}'
        return string