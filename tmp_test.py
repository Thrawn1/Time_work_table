from id_employee import *
from build_data_array import*

tmp = id_employee()
print(tmp)

a = {1:'op',2:'pp',3:'ap',4:'pa',5:'rr',6:'qq'}
j = 0 
while j != 10:
    j = j + 1
    if j in a.keys():
        print('Ок')
        print(j)
    else:
        print('Not Ok')
        print(j)

b = {1:{'a1':'sa'},2:{'a2':'sb'},3:{'a3':'sc'},4:{'a4':'sd'},5:{'a5':'se'},6:{'a6':'sf'}}
print(b)

for i in b.keys():
    k = 'a3'
    if k in b[i].keys():
        print('Ok')
    else:
        print(b[i])

file_name = '1_attlog.dat'
requested_year = int(input('Введите год:'))
requested_month = int(input('Введите месяц:'))
list_data = read_file_data(file_name,requested_year,requested_month)
data_array = build_data_array(list_data)
print(data_array)
t = data_array.keys()
print(t)