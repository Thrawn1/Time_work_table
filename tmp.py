from datetime import date,time
from class_file import lable,work_day

str_input = '        8	2021-12-07 05:45:41	1	255	1	0'
lable_work = lable(str_input)
work_day_1 = work_day(lable_work)
print(lable_work)
print(work_day_1.day_of_week)
print(work_day_1.define_loss_lable())
print(work_day_1.get_year(),type(work_day_1.get_year()))
print(work_day_1.get_month(),type(work_day_1.get_month()))
print(work_day_1.get_day(),type(work_day_1.get_day()))
print(work_day_1.lable_come)

print(str_input[10:17])
test_str = str_input[10:17]
test_year = int(test_str[0:4])
test_month = int(test_str[5:7])
print(test_year,type(test_year))
print(test_month,type(test_month))