import unittest
from datetime import date as DT_date
from WorkMonth import WorkMonth

class TestWorkMonth(unittest.TestCase):

    def setUp(self):
        self.year = 2023
        self.month = 5
        self.work_month = WorkMonth(self.year, self.month)

    def test_initialization(self):
        self.assertEqual(self.work_month.year, self.year)
        self.assertEqual(self.work_month.month, self.month)
        self.assertIsInstance(self.work_month.workdays, list)
        self.assertIsInstance(self.work_month.weekends, list)

    def test_invalid_month(self):
        with self.assertRaises(ValueError):
            WorkMonth(self.year, 13)

    def test_invalid_year(self):
        with self.assertRaises(ValueError):
            WorkMonth(2101, self.month)

    def test_get_workdays(self):
        workdays = self.work_month.get_all_days_work_month()['workdays']
        self.assertTrue(all(weekday < 5 for weekday in [day.weekday() for day in workdays]))

    def test_get_weekends(self):
        weekends = self.work_month.get_all_days_work_month()['weekends']
        self.assertTrue(all(weekday >= 5 for weekday in [day.weekday() for day in weekends]))

    def test_insert_holidays(self):
        # Assuming holidays.toml contains {"date": "2023-05-01"}
        self.work_month._insert_holidays()
        holidays = [DT_date(2023, 5, 1)]
        self.assertTrue(all(holiday in self.work_month.weekends for holiday in holidays))

    def test_insert_postponed(self):
        # Assuming postponed_day.toml contains {"date": "2023-05-06"}
        self.work_month._insert_postponed()
        postponed_days = [DT_date(2023, 5, 6)]
        self.assertTrue(all(day in self.work_month.workdays for day in postponed_days))

    def test_workdays_count(self):
        workdays = self.work_month.get_all_days_work_month()['workdays']
        self.assertEqual(len(workdays), len(self.work_month.workdays))

    def test_weekends_count(self):
        weekends = self.work_month.get_all_days_work_month()['weekends']
        self.assertEqual(len(weekends), len(self.work_month.weekends))

    def test_holiday_removal_from_workdays(self):
        # Assuming holidays.toml contains {"date": "2023-05-01"}
        self.work_month._insert_holidays()
        self.assertNotIn(DT_date(2023, 5, 1), self.work_month.workdays)

    def test_postponed_addition_to_workdays(self):
        # Assuming postponed_day.toml contains {"date": "2023-05-06"}
        self.work_month._insert_postponed()
        self.assertIn(DT_date(2023, 5, 6), self.work_month.workdays)

    def test_holiday_addition_to_weekends(self):
        # Assuming holidays.toml contains {"date": "2023-05-01"}
        self.work_month._insert_holidays()
        self.assertIn(DT_date(2023, 5, 1), self.work_month.weekends)

    def test_postponed_removal_from_weekends(self):
        # Assuming postponed_day.toml contains {"date": "2023-05-06"}
        self.work_month._insert_postponed()
        self.assertNotIn(DT_date(2023, 5, 6), self.work_month.weekends)

    def test_load_toml_file_not_found(self):
        dates = self.work_month._load_toml('non_existent_file.toml')
        self.assertEqual(dates, [])

    def test_load_toml_invalid_format(self):
        with self.assertRaises(ValueError):
            self.work_month._load_toml('invalid_format.toml')

if __name__ == '__main__':
    unittest.main()
