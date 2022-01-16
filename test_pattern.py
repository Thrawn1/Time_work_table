from id_employee import id_employee
from random import randint
all_employee = id_employee(type_data=2)
print(all_employee)
test = []

for d in range(20):
    lint = randint(0,30)
    test.append(lint)
h = [1,3,4,5,6,8,7,2,27,123,324,2343,9,10,11,12]
for i in test:
    match i:
        case int() if i in all_employee[0] :
            print(all_employee[0][i])
            print('Руководители')
            print('\n\n\n')
        case int() if i in all_employee[1]:
            print(all_employee[1][i])
            print('Работники')
            print('\n\n\n')
        case int() if i in all_employee[2]:
            print(all_employee[2][i])
            print('Кладовщик')
            print('\n\n\n')
        case int() if i in all_employee[3]:
            print(all_employee[3][i])
            print('Живущий в цеху')
            print('\n\n\n')
