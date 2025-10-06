import React, { useEffect, useState } from 'react';
import WeatherDisplay from './components/WeatherDisplay';
import LocationInput from './components/LocationInput';
import { fetchWeatherData } from './services/weatherService';

function App() {
    const [weatherData, setWeatherData] = useState(null);
    const [location, setLocation] = useState('');
    const [error, setError] = useState('');

    // Function to fetch user's geolocation and weather data
    const getLocationAndWeather = () => {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { latitude, longitude } = position.coords;
                    fetchWeatherData({ latitude, longitude })
                        .then(data => {
                            setWeatherData(data);
                            setError('');
                        })
                        .catch(err => {
                            setError('Failed to fetch weather data');
                            console.error(err);
                        });
                },
                (error) => {
                    setError('Geolocation not available');
                    console.error(error);
                }
            );
        } else {
            setError('Geolocation not supported by this browser.');
        }
    };

    useEffect(() => {
        getLocationAndWeather();
    }, []);

    const handleLocationChange = (newLocation) => {
        setLocation(newLocation);
    };

    const handleFetchWeather = () => {
        fetchWeatherData(location)
            .then(data => {
                setWeatherData(data);
                setError('');
            })
            .catch(err => {
                setError('Failed to fetch weather data');
                console.error(err);
            });
    };

    return (
        <div className="App">
            <h1>Weather App</h1>
            {error && <p>{error}</p>}
            <LocationInput location={location} onLocationChange={handleLocationChange} onFetchWeather={handleFetchWeather} />
            <WeatherDisplay weatherData={weatherData} />
        </div>
    );
}

export default App;