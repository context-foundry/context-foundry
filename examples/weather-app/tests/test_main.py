import unittest
from backend.main import app

class WeatherAppTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self.app = app.test_client()
        self.app.testing = True

    def test_index_route(self):
        """Test that the index route serves the HTML page."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<title>Weather App</title>', response.data)

    def test_weather_api_with_valid_city(self):
        """Test the weather API with a valid city."""
        with app.test_client() as test_client:
            response = test_client.get('/api/weather?city=London')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("city", data)
            self.assertIn("temperature", data)
            self.assertIn("description", data)

    def test_weather_api_with_missing_city(self):
        """Test the weather API with no city parameter."""
        response = self.app.get('/api/weather')
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_weather_api_with_invalid_city(self):
        """Test the weather API with an invalid city name."""
        with app.test_client() as test_client:
            response = test_client.get('/api/weather?city=InvalidCityName12345')
            self.assertNotEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()