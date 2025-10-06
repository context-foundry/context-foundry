/**
 * Store module for managing application state.
 */
const Store = (() => {
    let state = {
        weather: null
    };

    return {
        getState: () => state,
        setWeather: (weather) => {
            state.weather = weather;
        }
    };
})();