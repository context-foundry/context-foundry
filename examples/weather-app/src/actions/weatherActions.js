// Action creators for fetching weather data

export const fetchWeatherRequest = () => ({
    type: 'FETCH_WEATHER_REQUEST',
});

export const fetchWeatherSuccess = (data) => ({
    type: 'FETCH_WEATHER_SUCCESS',
    payload: data,
});

export const fetchWeatherFailure = (error) => ({
    type: 'FETCH_WEATHER_FAILURE',
    payload: error,
});

// Thunk action to fetch weather data
export const fetchWeather = (location) => {
    return async (dispatch) => {
        dispatch(fetchWeatherRequest());
        try {
            const response = await fetch(`https://api.weatherapi.com/v1/current.json?key=${process.env.REACT_APP_WEATHER_API_KEY}&q=${location}`);
            const data = await response.json();
            dispatch(fetchWeatherSuccess(data));
        } catch (error) {
            dispatch(fetchWeatherFailure(error.message));
        }
    };
};