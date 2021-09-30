from id_employer import id_employer
file_name = ''
tmp = id_employer()
print(tmp)
print('\n\n\n')
tmp_2 = id_employer(type_data=2)
tmp_1 = tmp_2[1]
print(tmp_1)
a = {1:'Родыгин', 2:'Пигин'}
b = {1:'Родыгин', 2:'Пигин',3:'Середнев'}
print(a)
print(b)
for i in a.keys():
    for ii in b.keys():
        if i == ii:
            print('Истина\n\n\n')
            print(i)
            print(a[ii])
            print('Проверка\n\n\n\n')
        else:
            print('Ложь\n\n\n')
            print(i)
            print(ii)
            print(a[i])
            print(b[ii])
