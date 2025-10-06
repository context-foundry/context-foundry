// Root reducer combining all reducers
import { combineReducers } from 'redux';
import weatherReducer from './weatherReducer';

// Combine all individual reducers into a root reducer
const rootReducer = combineReducers({
    weather: weatherReducer,
});

export default rootReducer;