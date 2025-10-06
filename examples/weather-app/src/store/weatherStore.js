import React, { createContext, useContext, useReducer } from 'react';
import { fetchWeatherData } from '../services/weatherService';

// Initial state
const initialState = {
  weatherData: null,
  error: null,
};

// Action types
const SET_WEATHER = 'SET_WEATHER';
const SET_ERROR = 'SET_ERROR';

// Reducer function
const weatherReducer = (state, action) => {
  switch (action.type) {
    case SET_WEATHER:
      return { ...state, weatherData: action.payload, error: null };
    case SET_ERROR:
      return { ...state, error: action.payload };
    default:
      return state;
  }
};

// Create context
const WeatherContext = createContext();

// Provider component
export const WeatherProvider = ({ children }) => {
  const [state, dispatch] = useReducer(weatherReducer, initialState);

  const fetchWeather = async (location) => {
    try {
      const data = await fetchWeatherData(location);
      dispatch({ type: SET_WEATHER, payload: data });
    } catch (error) {
      dispatch({ type: SET_ERROR, payload: error.message });
    }
  };

  return (
    <WeatherContext.Provider value={{ ...state, fetchWeather }}>
      {children}
    </WeatherContext.Provider>
  );
};

// Custom hook to use the weather context
export const useStore = () => {
  return useContext(WeatherContext);
};