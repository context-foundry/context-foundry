// Redux store configuration for the weather application

import { createStore, applyMiddleware } from 'redux';
import thunk from 'redux-thunk';
import rootReducer from './reducers';

// Create a Redux store with the rootReducer and apply middleware
const store = createStore(rootReducer, applyMiddleware(thunk));

export default store;