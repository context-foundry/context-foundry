const express = require('express');
const cors = require('cors');
const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Sample route
app.get('/api/weather', (req, res) => {
  // Mock weather data
  const weatherData = {
    location: 'New York',
    temperature: '20°C',
    condition: 'Clear'
  };
  res.json(weatherData);
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});