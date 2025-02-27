from dat_file_module import DatFileProcessor
from db_manager import DBManager
from interactive import post_data_employee
from Workday import Workday
import pickle

db_file_name = "employees.db"
db_manager = DBManager(db_file_name)
#db_interface = post_data_employee(db_file_name)

processor = DatFileProcessor()
file_path = "1_attlog.dat"
records = processor.read_dat_file(file_path, target_period=(2023, 5))
print(f'Всего записей: {len(records)}')
print(f'Первая запись: {records[0]}')
pickle_file = "records.pickle"
with open(pickle_file, "wb") as f:
    pickle.dump(records, f)