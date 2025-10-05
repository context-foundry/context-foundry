/**
 * Weather Service - Business Logic Layer
 * PROBLEM: Configured for premium API features
 */

import axios from 'axios';
import { 
  ENDPOINTS, 
  REQUEST_CONFIG, 
  buildApiUrl, 
  validateResponse 
} from './weatherAPI.js';

/**
 * Weather Service Class
 * ISSUE: Implements premium-tier functionality
 */
class WeatherService {
  constructor() {
    this.cache = new Map();
    this.rateLimitRemaining = 1000000;  // Premium rate limit
    this.lastRequestTime = 0;
  }

  /**
   * Get current weather data
   * PROBLEM: Uses premium endpoint and expects premium response
   * @param {string} location - Location to get weather for
   * @returns {Promise<Object>} Weather data
   */
  async getCurrentWeather(location) {
    try {
      const cacheKey = `current_${location}`;
      
      // Check cache first
      if (this.cache.has(cacheKey)) {
        const cached = this.cache.get(cacheKey);
        if (Date.now() - cached.timestamp < 300000) { // 5 min cache
          return cached.data;
        }
      }

      // PROBLEM: Premium endpoint call
      const url = buildApiUrl(ENDPOINTS.current, { 
        q: location,
        aqi: 'yes',    // Premium feature
        alerts: 'yes'  // Premium feature
      });

      console.log('Calling premium weather API:', url);

      const response = await axios.get(url, {
        ...REQUEST_CONFIG,
        timeout: 15000  // Premium timeout
      });

      if (!validateResponse(response)) {
        throw new Error('Invalid premium API response format');
      }

      // ISSUE: Processing premium-specific data
      const weatherData = this.processWeatherData(response.data);
      
      // Cache the result
      this.cache.set(cacheKey, {
        data: weatherData,
        timestamp: Date.now()
      });

      return weatherData;

    } catch (error) {
      console.error('Premium weather API error:', error);
      
      // PROBLEM: Error handling assumes premium tier errors
      if (error.response?.status === 403) {
        throw new Error('Premium API access denied - subscription expired');
      }
      
      if (error.response?.status === 429) {
        throw new Error('Premium API rate limit exceeded');
      }

      throw new Error(`Weather service error: ${error.message}`);
    }
  }

  /**
   * Get weather forecast
   * PROBLEM: Requests 10-day forecast (premium feature)
   * @param {string} location - Location
   * @param {number} days - Number of days (default 10 for premium)
   * @returns {Promise<Object>} Forecast data
   */
  async getForecast(location, days = 10) {  // Premium: 10 days
    try {
      const url = buildApiUrl(ENDPOINTS.forecast, {
        q: location,
        days: days,
        aqi: 'yes',      // Premium
        alerts: 'yes'    // Premium
      });

      const response = await axios.get(url, REQUEST_CONFIG);

      if (!validateResponse(response)) {
        throw new Error('Invalid premium forecast response');
      }

      return this.processForecastData(response.data);

    } catch (error) {
      console.error('Premium forecast API error:', error);
      throw new Error(`Forecast service error: ${error.message}`);
    }
  }

  /**
   * Process weather data from premium API
   * PROBLEM: Expects premium data fields
   * @param {Object} data - Raw API response
   * @returns {Object} Processed weather data
   */
  processWeatherData(data) {
    return {
      location: {
        name: data.location.name,
        region: data.location.region,
        country: data.location.country,
        lat: data.location.lat,
        lon: data.location.lon,
        timezone: data.location.tz_id
      },
      current: {
        temperature: data.current.temp_c,
        condition: data.current.condition.text,
        icon: data.current.condition.icon,
        humidity: data.current.humidity,
        windSpeed: data.current.wind_kph,
        windDirection: data.current.wind_dir,
        pressure: data.current.pressure_mb,
        visibility: data.current.vis_km,
        uv: data.current.uv,
        feelsLike: data.current.feelslike_c
      },
      // PROBLEM: Premium-only fields
      airQuality: data.current.air_quality ? {
        co: data.current.air_quality.co,
        no2: data.current.air_quality.no2,
        o3: data.current.air_quality.o3,
        so2: data.current.air_quality.so2,
        pm2_5: data.current.air_quality.pm2_5,
        pm10: data.current.air_quality.pm10,
        usEpaIndex: data.current.air_quality['us-epa-index'],
        gbDefraIndex: data.current.air_quality['gb-defra-index']
      } : null,
      alerts: data.alerts?.alert || [],  // Premium field
      lastUpdated: data.current.last_updated
    };
  }

  /**
   * Process forecast data from premium API
   * PROBLEM: Handles 10-day premium forecast
   * @param {Object} data - Raw forecast response
   * @returns {Object} Processed forecast data
   */
  processForecastData(data) {
    const currentData = this.processWeatherData(data);
    
    return {
      ...currentData,
      forecast: data.forecast.forecastday.map(day => ({
        date: day.date,
        maxTemp: day.day.maxtemp_c,
        minTemp: day.day.mintemp_c,
        condition: day.day.condition.text,
        icon: day.day.condition.icon,
        chanceOfRain: day.day.daily_chance_of_rain,
        avgHumidity: day.day.avghumidity,
        maxWind: day.day.maxwind_kph,
        uv: day.day.uv,
        // PROBLEM: Premium hourly data
        hourly: day.hour.map(hour => ({
          time: hour.time,
          temp: hour.temp_c,
          condition: hour.condition.text,
          icon: hour.condition.icon,
          windSpeed: hour.wind_kph,
          humidity: hour.humidity,
          chanceOfRain: hour.chance_of_rain
        }))
      }))
    };
  }

  /**
   * Clear cache
   */
  clearCache() {
    this.cache.clear();
  }
}

// Export singleton instance
export default new WeatherService();