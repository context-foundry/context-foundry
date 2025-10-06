# Main backend file for the weather-app
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    """
    Default route that confirms the server is running.
    """
    return jsonify({"message": "Welcome to the Weather App API!"})

@app.route('/weather', methods=['GET'])
def get_weather():
    """
    A placeholder route for getting weather data.
    """
    example_data = {
        "city": "New York",
        "temperature": "15°C",
        "condition": "Cloudy"
    }
    return jsonify(example_data)

if __name__ == '__main__':
    app.run(debug=True)