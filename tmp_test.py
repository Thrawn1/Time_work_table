from determination_period import*
from build_data_array import*
from read_file_data import*
from datetime import datetime
from analyze_data import*
from calendar import calendar, weekday, monthrange
from search_missed_day import*
import random
import calendar
file_name = '1_attlog.dat'
delta_month = random.randint(0,12)
delta_year = random.randint(0,5)
requested_month = int((datetime.now()).month)-delta_month
requested_year = int((datetime.now()).year)-delta_year
print(requested_year,requested_month,sep='|||')
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
# print(data_array)
all_day_month = list(range(1,(int(monthrange(requested_year,requested_month)[1])+1),1))
search_for_missed_day(data_array,all_day_month,requested_year,requested_month)
last_day_month = monthrange(requested_year,requested_month)[1]
search_missing_mark_employee(data_array,last_day_month,requested_year,requested_month)
#analyze_employee_work_date(data_array)
print('Готово!')
# last_day_month = calendar.monthrange(requested_year,requested_month)[1]
# list_days_of_month = list(range(1,last_day_month+1,1))
# print(last_day_month)
# print(list_days_of_month)
#last_day = monthrange(int(year_input), int(month_input))
#jl = weekday(year_input,month_input,last_day[1])
#print(last_day,type(last_day),sep='||')
#print(jl,type(jl),sep='||')
#print(A[8:10])
#print(A[11:30])
#print(A[11:21])