from flask import Flask, jsonify, render_template, request
import requests

app = Flask(__name__)

# Replace with your actual OpenWeatherMap API key
API_KEY = "your_openweathermap_api_key"

@app.route("/")
def index():
    """Render the main page."""
    return render_template("index.html")

@app.route("/api/weather", methods=["GET"])
def get_weather():
    """
    Fetch and return weather data for a given city.
    Requires a 'city' query parameter in the request.
    """
    city = request.args.get("city")
    if not city:
        return jsonify({"error": "City is required"}), 400

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()
        weather_data = response.json()
        return jsonify({
            "city": weather_data["name"],
            "temperature": weather_data["main"]["temp"],
            "description": weather_data["weather"][0]["description"],
            "icon": weather_data["weather"][0]["icon"]
        })
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)