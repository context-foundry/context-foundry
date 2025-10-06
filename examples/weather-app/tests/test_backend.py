# Test file for the backend of the weather-app
import unittest
from backend.main import app

class TestBackend(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_home(self):
        """
        Test the '/' route of the API.
        """
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome to the Weather App API!", response.data)

    def test_get_weather(self):
        """
        Test the '/weather' route of the API.
        """
        response = self.app.get('/weather')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("city", data)
        self.assertIn("temperature", data)
        self.assertIn("condition", data)

if __name__ == '__main__':
    unittest.main()