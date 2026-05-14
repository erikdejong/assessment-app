import unittest


class TestExample(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(1 + 1, 2)
