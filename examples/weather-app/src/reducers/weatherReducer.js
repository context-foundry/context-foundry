// src/reducers/weatherReducer.js

const initialState = {
    weatherData: null,
    loading: false,
    error: null,
};

// Action types
const FETCH_WEATHER_REQUEST = 'FETCH_WEATHER_REQUEST';
const FETCH_WEATHER_SUCCESS = 'FETCH_WEATHER_SUCCESS';
const FETCH_WEATHER_FAILURE = 'FETCH_WEATHER_FAILURE';

// Reducer
const weatherReducer = (state = initialState, action) => {
    switch (action.type) {
        case FETCH_WEATHER_REQUEST:
            return { ...state, loading: true, error: null };
        case FETCH_WEATHER_SUCCESS:
            return { ...state, loading: false, weatherData: action.payload };
        case FETCH_WEATHER_FAILURE:
            return { ...state, loading: false, error: action.payload };
        default:
            return state;
    }
};

export const fetchWeatherRequest = () => ({ type: FETCH_WEATHER_REQUEST });
export const fetchWeatherSuccess = (data) => ({ type: FETCH_WEATHER_SUCCESS, payload: data });
export const fetchWeatherFailure = (error) => ({ type: FETCH_WEATHER_FAILURE, payload: error });

// Async action to fetch weather data
export const fetchWeatherData = (location) => {
    return async (dispatch) => {
        dispatch(fetchWeatherRequest());
        try {
            const response = await fetch(`https://api.example.com/weather?location=${location}`); // Replace with actual API endpoint
            const data = await response.json();
            dispatch(fetchWeatherSuccess(data));
        } catch (error) {
            dispatch(fetchWeatherFailure(error.message));
        }
    };
};

export default weatherReducer;