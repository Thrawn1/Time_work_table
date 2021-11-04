import sys
import datetime
sys.path.append('..')
import build_data_array 


name_file_for_test = 'test_read_file.dat'
def test_bloc_buil_data_array_all():
    requested_year = 2021 
    requested_month = 3
    list_data = build_data_array.read_file_data(name_file_for_test,requested_year,requested_month)
    calculated_data = build_data_array.build_data_array(list_data)
    expected_result ={'2021-03-01': {8: [datetime.datetime(2021, 3, 1, 5, 55), datetime.datetime(2021, 3, 1, 5, 55), 'work'], 4: [datetime.datetime(2021, 3, 1, 17, 0), datetime.datetime(2021, 3, 1, 6, 30), 'work'], 5: [datetime.datetime(2021, 3, 1, 14, 0), datetime.datetime(2021, 3, 1, 6, 45, 15), 'work'], 6: [datetime.datetime(2021, 3, 1, 15, 0), datetime.datetime(2021, 3, 1, 7, 0), 'work'], 9: [datetime.datetime(2021, 3, 1, 16, 0), datetime.datetime(2021, 3, 1, 7, 30, 10), 'work'], 3: [datetime.datetime(2021, 3, 1, 18, 0), datetime.datetime(2021, 3, 1, 8, 0), 'work']}}
    assert calculated_data == expected_result