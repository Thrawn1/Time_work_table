import datetime



class Workday():
    def __init__(self, date:datetime.date, employee_id:int):
        self.employee_id = employee_id
        self.start_time = None
        self.end_time = None
        self.date = date
        self.is_weekend = False
        self.is_vacation = False
        self.is_sick_leave = False
        self.raw_lines = []


    def check_missing_mark(self):
        if self.start_time == self.end_time:
            return True
    def get_workday_hours(self):
        if self.start_time == self.end_time:
            return 0
        return (self.end_time - self.start_time).seconds / 3600
    def __str__(self):
        return f"Workday: {self.date} {self.time} {self.employee_id}"