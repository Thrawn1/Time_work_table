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
    
    def build_day_object(self):
        """Данный метод создает объекты класса day"""
        for line in self.month_data_raw:
            id_row = int(line[7:10])
            if id_row not in self.work_employees:
                self.work_employees[id_row] = Employee(id_row)
                self.month_data[id_row] = []
            obj_lable = Lable(line)
            flag_chek_day = self.check_day_in_list_month(id_row, obj_lable.get_day())
            if flag_chek_day == False:
                obj_day = Work_day(obj_lable)
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
        with open(path_file_postponed_works_days,'r',encoding='utf-8') as file:
            for line in file:
                line = line.rstrip('\n')
                str_line = line.split('.')
                srt_line_1 = [int(i) for i in str_line]
                if line[1] == self.month:
                    list_obj_postponed_works_days.append(srt_line_1[0])
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

    def check_loss_days_in_work_month(self):
        """Данный метод проверяет, есть ли пропущенные дни в месяце"""
        mandatory_business_days_of_the_month = self._get_all_work_days_months_ideally()
        for id in self.month_data.keys():
            for day in self.month_data[id]:
                day_int = day.get_day()
                try:
                    mandatory_business_days_of_the_month.remove(day_int)
                except ValueError:
                    pass
            self.loss_all_data_days[id] = mandatory_business_days_of_the_month

    def __str__(self) -> str:
        """Данный метод возвращает строку с данными за месяц"""
        work_employees = ' '
        for id in self.work_employees:
            work_employees += self.work_employees[id].info() + ', '
        work_employees = work_employees[:-2]
        string = f' Месяц: {self.month_name} {self.year} года.\n Работники: {work_employees}.\n Данные за месяц: {self.month_data}'
        return string

    
    def _search_object_day(self,id,day):
        """Данный метод возвращает объект класса Day"""
        for day_obj in self.month_data[id]:
            if day_obj.get_day() == day:
                return day_obj

    def _display_info_loss_lable(self,id):
        if id in self.loss_lable_days:
            if len(self.loss_lable_days[id]) != 0:
                print(f'Работник {self.work_employees[id].get_name()} {self.work_employees[id].get_family()} пропустил метки в дни:')
                for day in self.loss_lable_days[id]:
                    data_obj = self._search_object_day(id,day)
                    print(f'{data_obj} Метка: {data_obj.get_go()}')
    
    def _display_info_loss_day(self,id):
        names_weekdays = ('Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье')
        months_name = ('Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь')
        if id in self.loss_all_data_days:
            if len(self.loss_all_data_days[id]) != 0:
                print(f'Работник {self.work_employees[id].get_name()} {self.work_employees[id].get_family()} пропустил данные в дни:')
                for day in self.loss_all_data_days[id]:
                    date_obj = date(self.year,self.month,day)
                    day_name = date_obj.weekday()
                    info_day = str(date_obj.day) + ' ' + months_name[self.month-1] + ' ' + str(self.year) +' ' + names_weekdays[day_name]
                    print(info_day)
    
    def _generate_lists_exclusion(self):
        """Данный метод генерирует списки исключений и проживающих в цеху"""
        for id in self.work_employees:
            role = self.work_employees[id].get_role()
            print(role)

    def display_info_loss_data (self):
        """Данный метод выводит информацию о пропущенных днях"""
        for id in self.work_employees:
            role_name = self.work_employees[id].get_role()
            if role_name != 'Руководитель' and role_name != 'Кладовщик':
                self._display_info_loss_lable(id)
                self._display_info_loss_day(id)

    def _edit_data_day_employee(self,id,day):
        """Данный метод редактирует данные о дне для конкретного работника"""
        for day_obj in self.month_data[id]:
            if day_obj.get_day() == day:
                day_obj.edit_data(go,leave)
                break