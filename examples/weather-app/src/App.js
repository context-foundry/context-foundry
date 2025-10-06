import React, { useState } from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';
import WeatherCard from './components/WeatherCard';

const App = () => {
    const [location, setLocation] = useState('');
    const [weatherData, setWeatherData] = useState(null);

    const handleSearch = (e) => {
        e.preventDefault();
        // Here you would typically fetch weather data based on the location
        // Mocking the data for demonstration purposes
        const mockWeather = {
            location: location,
            temperature: '22°C',
            description: 'Sunny',
        };
        setWeatherData(mockWeather);
    };

    return (
        <div className="container mt-5">
            <h1 className="text-center">Weather App</h1>
            <form className="mb-4" onSubmit={handleSearch}>
                <div className="input-group">
                    <input
                        type="text"
                        className="form-control"
                        placeholder="Enter location"
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                    />
                    <button className="btn btn-primary" type="submit">
                        Search
                    </button>
                </div>
            </form>
            {weatherData && <WeatherCard data={weatherData} />}
        </div>
    );
};

export default App;