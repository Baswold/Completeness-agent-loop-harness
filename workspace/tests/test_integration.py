import unittest
from src.main import greet

class TestIntegration(unittest.TestCase):
    def test_integration_with_other_function(self):
        # Simulate another function that uses greet
        def integrated_function(name):
            return greet(name)

        # Test cases for the integrated function
        self.assertEqual(integrated_function('Alice'), 'Hello, Alice!')
        self.assertEqual(integrated_function(None), 'Hello, Guest!')
        self.assertEqual(integrated_function('     '), 'Hello, Stranger!')  # Verify whitespace handling
        self.assertEqual(integrated_function(123), 'Hello, Guest!')  # Non-string input

if __name__ == '__main__':
    unittest.main()