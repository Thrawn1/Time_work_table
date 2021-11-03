import sys
import datetime
sys.path.append('..')
from analyze_data import reading_employee_work_date


def test_reading_employee_work_date_null():
    request_dict = {}
    request_id = 5
    calculated_data = reading_employee_work_date(request_dict,request_id)
    expected_result = []
    assert calculated_data == expected_result

def test_reading_employee_work_date_good():
    request_dict = {'2021-03-01': {8: [datetime.datetime(2021, 3, 1, 5, 55), datetime.datetime(2021, 3, 1, 5, 55), 'work'], 4: [datetime.datetime(2021, 3, 1, 17, 0), datetime.datetime(2021, 3, 1, 6, 30), 'work'], 5: [datetime.datetime(2021, 3, 1, 14, 0), datetime.datetime(2021, 3, 1, 6, 45, 15), 'work'], 6: [datetime.datetime(2021, 3, 1, 15, 0), datetime.datetime(2021, 3, 1, 7, 0), 'work'], 9: [datetime.datetime(2021, 3, 1, 16, 0), datetime.datetime(2021, 3, 1, 7, 30, 10), 'work'], 3: [datetime.datetime(2021, 3, 1, 18, 0), datetime.datetime(2021, 3, 1, 8, 0), 'work']}}
    request_id_list = [4,5,6,9,3]
    for request_id in request_id_list:
        calculated_data = reading_employee_work_date(request_dict,request_id)
        expected_result = ['2021-03-01']
        assert calculated_data == expected_result