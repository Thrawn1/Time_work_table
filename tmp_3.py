import toml
a = ['2020-01', '2020-02', '2020-03', '2020-04', '2020-05', '2020-06', '2020-07',
      '2020-08', '2020-09', '2020-10', '2020-11', '2020-12']
b = ['2020-01', '2021-02', '2020-03', '2020-04', '2020-05', '2020-06', '2020-07',
      '2020-08', '2022-09', '2020-10', '2020-11', '2020-12']

c = set(a) - set(b)


def screening_row(screen_condition:set,ame_file_data_label:str) -> list:
    for condition in screen_condition:
        year = condition[:4]
        month = condition[5:]
        print(f"Год: {year}, месяц: {month}")

screening_row(c, '1_attlog.dat')

with open('company_data_real copy.toml', 'r', encoding='utf-8') as file:
    data = toml.load(file)



print(data)
# print(data['roles'])
# print(data['employees'])