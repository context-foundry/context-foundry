import axios from 'axios';

const API_KEY = process.env.REACT_APP_WEATHER_API_KEY; // Ensure this key is defined in .env

export const fetchWeatherData = async (location) => {
  const response = await axios.get(`https://api.weatherapi.com/v1/current.json?key=${API_KEY}&q=${location}`);
  return response.data;
};