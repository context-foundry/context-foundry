// Tests for weather actions

import configureMockStore from 'redux-mock-store';
import thunk from 'redux-thunk';
import { fetchWeather, fetchWeatherSuccess, fetchWeatherRequest, fetchWeatherFailure } from '../actions/weatherActions';

const middlewares = [thunk];
const mockStore = configureMockStore(middlewares);

describe('Weather Actions', () => {
    it('should create FETCH_WEATHER_REQUEST action', () => {
        const expectedAction = { type: 'FETCH_WEATHER_REQUEST' };
        expect(fetchWeatherRequest()).toEqual(expectedAction);
    });

    it('should create FETCH_WEATHER_SUCCESS action', () => {
        const data = { location: { name: 'London' }, current: { temp_c: 15, condition: { text: 'Sunny' } } };
        const expectedAction = { type: 'FETCH_WEATHER_SUCCESS', payload: data };
        expect(fetchWeatherSuccess(data)).toEqual(expectedAction);
    });

    it('should create FETCH_WEATHER_FAILURE action', () => {
        const error = 'Error fetching weather data';
        const expectedAction = { type: 'FETCH_WEATHER_FAILURE', payload: error };
        expect(fetchWeatherFailure(error)).toEqual(expectedAction);
    });
});

describe('fetchWeather async action', () => {
    it('creates FETCH_WEATHER_SUCCESS when fetching weather has been done', async () => {
        const store = mockStore({});
        const location = 'London';

        await store.dispatch(fetchWeather(location));
        const actions = store.getActions();

        expect(actions[0]).toEqual({ type: 'FETCH_WEATHER_REQUEST' });
        expect(actions[1].type).toEqual('FETCH_WEATHER_SUCCESS');
    });
});