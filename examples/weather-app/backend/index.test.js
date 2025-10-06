// Importing necessary modules for testing
const request = require('supertest');
const express = require('express');
const axios = require('axios');
const dotenv = require('dotenv');

dotenv.config();
const app = express();
const API_KEY = process.env.WEATHER_API_KEY;

// Mocking axios
jest.mock('axios');

describe('Weather API', () => {
    it('should return weather data for a valid city', async () => {
        const city = 'London';
        const mockResponse = {
            data: {
                name: 'London',
                main: {
                    temp: 15,
                    pressure: 1012,
                },
                weather: [{ description: 'clear sky' }],
            },
        };

        axios.get.mockResolvedValue(mockResponse);
        
        const response = await request(app).get(`/api/weather?city=${city}`);

        expect(response.status).toBe(200);
        expect(response.body.name).toBe('London');
        expect(response.body.main.temp).toBe(15);
    });

    it('should return an error when city is not provided', async () => {
        const response = await request(app).get('/api/weather');

        expect(response.status).toBe(400);
        expect(response.body.error).toBe('City parameter is required');
    });

    it('should return an error when the city does not exist', async () => {
        const city = 'UnknownCity';
        axios.get.mockRejectedValueOnce({
            response: {
                status: 404,
                data: { message: 'city not found' },
            },
        });

        const response = await request(app).get(`/api/weather?city=${city}`);

        expect(response.status).toBe(404);
        expect(response.body.error).toBe('city not found');
    });
});