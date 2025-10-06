// Importing necessary modules
const express = require('express');
const axios = require('axios');
const dotenv = require('dotenv');

// Load environment variables from .env file
dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;
const API_KEY = process.env.WEATHER_API_KEY; // Ensure this key is set in your environment

// Endpoint to get weather data
app.get('/api/weather', async (req, res) => {
    const { city } = req.query; // Get city from query parameters
    if (!city) {
        return res.status(400).json({ error: 'City parameter is required' });
    }

    // Call to OpenWeatherMap API
    try {
        const response = await axios.get(`https://api.openweathermap.org/data/2.5/weather`, {
            params: {
                q: city,
                appid: API_KEY,
                units: 'metric' // Change to 'imperial' for Fahrenheit
            }
        });
        res.json(response.data); // Send back the data received from the API
    } catch (error) {
        console.error(error);
        if (error.response) {
            // Client received an error response (5xx, 4xx)
            return res.status(error.response.status).json({ error: error.response.data.message });
        } else if (error.request) {
            // Client never received a response, or request never left
            return res.status(500).json({ error: 'Error with the request' });
        } else {
            // Anything else
            return res.status(500).json({ error: error.message });
        }
    }
});

// Start the server
app.listen(PORT, () => {
    console.log(`Server is running on http://localhost:${PORT}`);
});