import sys
import datetime
sys.path.append('..')
from build_data_array import build_data_array


def test_build_array_good():
    request_list = ['        8	2021-03-01 05:55:00	1	255	1	0\n',
    '        4	2021-03-01 06:30:00	1	255	1	0\n',
    '        5	2021-03-01 06:45:15	1	255	1	0\n',
    '        6	2021-03-01 07:00:00	1	255	1	0\n',
    '        9	2021-03-01 07:30:10	1	255	1	0\n',
    '        3	2021-03-01 08:00:00	1	255	1	0\n',
    '        5	2021-03-01 14:00:00	1	255	1	0\n',
    '        6	2021-03-01 15:00:00	1	255	1	0\n',
    '        9	2021-03-01 16:00:00	1	255	1	0\n',
    '        4	2021-03-01 17:00:00	1	255	1	0\n',
    '        3	2021-03-01 18:00:00	1	255	1	0\n']
    calculated_data = build_data_array(request_list)
    expected_result ={'2021-03-01': {8: [datetime.datetime(2021, 3, 1, 5, 55), datetime.datetime(2021, 3, 1, 5, 55), 'work'], 4: [datetime.datetime(2021, 3, 1, 17, 0), datetime.datetime(2021, 3, 1, 6, 30), 'work'], 5: [datetime.datetime(2021, 3, 1, 14, 0), datetime.datetime(2021, 3, 1, 6, 45, 15), 'work'], 6: [datetime.datetime(2021, 3, 1, 15, 0), datetime.datetime(2021, 3, 1, 7, 0), 'work'], 9: [datetime.datetime(2021, 3, 1, 16, 0), datetime.datetime(2021, 3, 1, 7, 30, 10), 'work'], 3: [datetime.datetime(2021, 3, 1, 18, 0), datetime.datetime(2021, 3, 1, 8, 0), 'work']}}
    assert calculated_data == expected_result


def test_build_array_duplicate_marks():
    request_list = ['        8	2021-03-01 05:55:00	1	255	1	0\n',
    '        4	2021-03-01 06:30:00	1	255	1	0\n',
    '        4	2021-03-01 06:31:01	1	255	1	0\n',
    '        5	2021-03-01 06:45:15	1	255	1	0\n',
    '        5	2021-03-01 06:55:11	1	255	1	0\n',
    '        6	2021-03-01 07:00:00	1	255	1	0\n',
    '        6	2021-03-01 07:00:01	1	255	1	0\n',
    '        9	2021-03-01 07:29:59	1	255	1	0\n',
    '        9	2021-03-01 07:30:10	1	255	1	0\n',
    '        3	2021-03-01 08:00:00	1	255	1	0\n',
    '        3	2021-03-01 08:00:02	1	255	1	0\n',
    '        5	2021-03-01 14:00:00	1	255	1	0\n',
    '        6	2021-03-01 15:00:00	1	255	1	0\n',
    '        9	2021-03-01 16:00:00	1	255	1	0\n',
    '        4	2021-03-01 17:00:00	1	255	1	0\n',
    '        3	2021-03-01 17:59:01	1	255	1	0\n',
    '        3	2021-03-01 18:00:00	1	255	1	0\n']
    calculated_data = build_data_array(request_list)
    expected_result ={'2021-03-01': {8: [datetime.datetime(2021, 3, 1, 5, 55), datetime.datetime(2021, 3, 1, 5, 55), 'work'], 4: [datetime.datetime(2021, 3, 1, 17, 0), datetime.datetime(2021, 3, 1, 6, 30), 'work'], 5: [datetime.datetime(2021, 3, 1, 14, 0), datetime.datetime(2021, 3, 1, 6, 45, 15), 'work'], 6: [datetime.datetime(2021, 3, 1, 15, 0), datetime.datetime(2021, 3, 1, 7, 0), 'work'], 9: [datetime.datetime(2021, 3, 1, 16, 0), datetime.datetime(2021, 3, 1, 7, 29, 59), 'work'], 3: [datetime.datetime(2021, 3, 1, 18, 0), datetime.datetime(2021, 3, 1, 8, 0), 'work']}}
    assert calculated_data == expected_result
