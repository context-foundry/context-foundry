// Entry point for the weather-app
import express from "express";
import axios from "axios";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;
const API_KEY = process.env.WEATHER_API_KEY;
const BASE_API_URL = process.env.BASE_API_URL;

// Middleware to serve static files and parse JSON
app.use(express.json());

// API route to fetch weather data
app.get("/api/weather/:city", async (req, res) => {
  const city = req.params.city;

  try {
    const response = await axios.get(
      `${BASE_API_URL}weather?q=${city}&appid=${API_KEY}`
    );
    res.json(response.data);
  } catch (error) {
    console.error("Error fetching weather data:", error.message);
    res.status(error.response?.status || 500).json({
      error: "Unable to fetch weather data. Please try again later."
    });
  }
});

// Root route for testing
app.get("/", (req, res) => {
  res.send("Welcome to the Weather App!");
});

// Start the server
app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});