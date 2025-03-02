import unittest
import calendar
from WorkMonth import WorkMonth

class TestWorkMonth(unittest.TestCase):
    
    def test_get_weekends_february_2023(self):
        """Test weekend days in February 2023"""
        work_month = WorkMonth(2023, 2)
        
        # February 2023 has 28 days with the following weekends:
        # Feb 4-5, 11-12, 18-19, 25-26 (8 days total)
        expected_weekends = [4, 5, 11, 12, 18, 19, 25, 26]
        
        # Re-calculate weekends directly to avoid using the value set in __init__
        weekends = work_month._get_weekends(2, 2023)
        
        self.assertEqual(set(weekends), set(expected_weekends))
        self.assertEqual(len(weekends), 8)
    
    def test_get_weekends_january_2024(self):
        """Test weekend days in January 2024"""
        work_month = WorkMonth(2024, 1)
        
        # January 2024 has 31 days with the following weekends:
        # Jan 6-7, 13-14, 20-21, 27-28 (8 days total)
        expected_weekends = [6, 7, 13, 14, 20, 21, 27, 28]
        
        weekends = work_month._get_weekends(1, 2024)
        
        self.assertEqual(set(weekends), set(expected_weekends))
        self.assertEqual(len(weekends), 8)
    
    def test_get_weekends_parameter_order(self):
        """Test that parameter order (month, year) is handled correctly"""
        work_month = WorkMonth(2023, 5)
        
        # Testing that the method uses self.year and self.month rather than parameters
        # May 2023 weekend days: 6-7, 13-14, 20-21, 27-28 (8 days)
        expected_weekends = [6, 7, 13, 14, 20, 21, 27, 28]
        
        # Intentionally passing different values to see if method uses instance variables
        weekends = work_month._get_weekends(12, 2022)  # Should ignore these parameters
        
        self.assertEqual(set(weekends), set(expected_weekends))
    
    def test_get_weekends_leap_year(self):
        """Test weekends in February of leap year 2024"""
        work_month = WorkMonth(2024, 2)
        
        # February 2024 has 29 days with the following weekends:
        # Feb 3-4, 10-11, 17-18, 24-25 (8 days total)
        expected_weekends = [3, 4, 10, 11, 17, 18, 24, 25]
        
        weekends = work_month._get_weekends(2, 2024)
        
        self.assertEqual(set(weekends), set(expected_weekends))
        self.assertEqual(len(weekends), 8)

if __name__ == '__main__':
    unittest.main()