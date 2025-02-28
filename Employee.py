
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

    def displayEmployee(self):
        print(f"ID: {self.id}, Name: {self.first_name} {self.last_name}, Role: {self.role}, Hourly Rate: {self.hourly_rate}, Salary: {self.salary}")
    def add_workday(self, workday):
        self.workdays.append(workday)
    def calculate_monthly_salary(self):
        pass
    def check_missed_days(self):
        pass
    def get_full_info(self):
        return f"{self.first_name} {self.last_name}, {self.role}, {self.salary}"