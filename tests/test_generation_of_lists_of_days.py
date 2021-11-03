import sys
sys.path.append('..')
from analyze_data import generation_of_lists_of_days

def test_generation_of_lists_of_days():
    request_year = 2021
    request_month = 3
    calculated_data = generation_of_lists_of_days(request_year,request_month)
    expected_result = [['2021-03-01', '2021-03-02', '2021-03-03', '2021-03-04', '2021-03-05', '2021-03-09', '2021-03-10', '2021-03-11', '2021-03-12', '2021-03-15', '2021-03-16', '2021-03-17', '2021-03-18', '2021-03-19', '2021-03-22', '2021-03-23', '2021-03-24', '2021-03-25', '2021-03-26', '2021-03-29', '2021-03-30', '2021-03-31'], ['2021-03-06', '2021-03-07', '2021-03-08', '2021-03-13', '2021-03-14', '2021-03-20', '2021-03-21', '2021-03-27', '2021-03-28']]
    assert calculated_data == expected_result