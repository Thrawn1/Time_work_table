from db_manager import DBManager
from interactive import post_data_employee

db_file_name = "employees.db"
db_manager = DBManager(db_file_name)
db_interface = post_data_employee(db_file_name)