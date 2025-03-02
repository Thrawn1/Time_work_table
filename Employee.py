from datetime import date
class Employee:
    def __init__(self,employee_id, first_name, last_name,role, hourly_rate, workday_hours=8):
        self.id = employee_id
        self.last_name = last_name
        self.first_name = first_name
        self.salary = 0
        self.role = role
        self.hourly_rate = hourly_rate
        self.workday_hours = workday_hours
        self.workdays  = []

    def add_workday(self, workday):
        if self.search_by_workday(workday.date) is None:
            self.workdays.append(workday)
        else:
            print("Рабочий день уже добавлен")
    def calculate_monthly_salary(self):
        pass
    def check_missed_days(self):
        pass
    def search_by_workday(self, date:date):
        for workday in self.workdays:
            if workday.date == date:
                return workday
        return None