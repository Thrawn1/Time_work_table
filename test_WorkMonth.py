from WorkMonth import WorkMonth
from unittest import TestCase
import logging

class TestWorkMonth(TestCase):
    def setUp(self):
        # Disable logging during tests
        logging.disable(logging.CRITICAL)
        
    def tearDown(self):
        # Re-enable logging after tests
        logging.disable(logging.NOTSET)
        
    def test_init_valid_params(self):
        """Test initialization with valid parameters"""
        wm = WorkMonth(2023, 5)
        self.assertEqual(wm.year, 2023)
        self.assertEqual(wm.month, 5)
        self.assertTrue(len(wm.workdays) > 0)
        self.assertTrue(len(wm.weekends) > 0)
        
    def test_init_invalid_month(self):
        """Test initialization with invalid month number"""
        with self.assertRaises(ValueError) as context:
            WorkMonth(2023, 13)