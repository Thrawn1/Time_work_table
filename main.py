from dat_file_module import DatFileProcessor
from db_manager import DBManager
from Workday import Workday
from Employee import Employee



def check_employee(employees:list, employee_id:int) -> bool:
    for employee in employees:
        if employee.id == employee_id:
            return True
    return False
def get_data_from_db(employee_id:int, employees_db:list) -> tuple:
    for employee in employees_db:
        if employee['employee_id'] == employee_id:
            return employee

db_file_name = "employees.db"
db_manager = DBManager(db_file_name)
#db_interface = post_data_employee(db_file_name)

processor = DatFileProcessor()
file_path = "1_attlog.dat"
records = processor.read_dat_file(file_path, target_period=(2023, 5))
print(f'Всего записей: {len(records)}')
print(f'Первая запись: {records[0]}')
employees = []
employees_db = db_manager.get_all_employees()
for record in records:
    if not check_employee(employees, record.employee_id):
       id = record.employee_id
       data = get_data_from_db(id, employees_db)
       employees.append(Employee(id, data['first_name'], data['last_name'], data['role'], data['hourly_rate'], data['role_coefficient']))

for record in records:
    for employee in employees:
        if record.employee_id == employee.id:
            if employee.check_workday(record.timestamp.date()) == False:
                workday = Workday(record.timestamp.date(), employee.id)
                workday.add_time(record.timestamp.time())
                employee.workdays.append(workday)
            else:
                workday = employee.search_by_workday(record.timestamp.date())
                workday.add_time(record.timestamp.time())
                employee.workdays.append(workday)


for employee in employees:
    print(employee.workdays)
    for workday in employee.workdays:
        print(workday)
        if workday.check_missing_mark():
            print("Отсутствует отметка")
        else:
            print("Отметка есть")
    #employee.displayEmployee()