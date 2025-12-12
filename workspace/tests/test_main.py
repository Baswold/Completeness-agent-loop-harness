import unittest
from src.main import greet

class TestGreetFunction(unittest.TestCase):
    def test_greet_none_input(self):
        self.assertEqual(greet(None), 'Hello, Guest!')  # Input None

    def test_greet_empty_input(self):
        with self.assertRaises(TypeError):
            greet()  # Calling greet without any arguments

    def test_greet_empty_string(self):
        self.assertEqual(greet(''), 'Hello, Stranger!')  # Input empty string

    def test_greet_bytes_input(self):
        self.assertEqual(greet(b'byte'), 'Hello, Guest!')  # Input bytes

    def test_greet_object_input(self):
        self.assertEqual(greet(object()), 'Hello, Guest!')  # Input object

    def test_greet_numerical_input(self):
        self.assertEqual(greet(5), 'Hello, Guest!')  # Input numerical value

    def test_greet_multiple_consecutive_spaces(self):
        self.assertEqual(greet('     '), 'Hello, Stranger!')  # Input with multiple spaces

if __name__ == '__main__':
    unittest.main()
