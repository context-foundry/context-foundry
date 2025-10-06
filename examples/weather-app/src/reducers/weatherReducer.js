// Reducer for managing weather-related state

const initialState = {
    data: null,
    loading: false,
    error: null,
};

// Weather reducer function to handle actions
const weatherReducer = (state = initialState, action) => {
    switch (action.type) {
        case 'FETCH_WEATHER_REQUEST':
            return { ...state, loading: true, error: null };
        case 'FETCH_WEATHER_SUCCESS':
            return { ...state, loading: false, data: action.payload };
        case 'FETCH_WEATHER_FAILURE':
            return { ...state, loading: false, error: action.payload };
        default:
            return state;
    }
};

export default weatherReducer;