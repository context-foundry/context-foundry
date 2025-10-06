const request = require('supertest');
const express = require('express');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

app.get('/api/weather', (req, res) => {
  res.json({
    location: 'New York',
    temperature: '20°C',
    condition: 'Clear'
  });
});

describe('GET /api/weather', () => {
  it('should return weather data', async () => {
    const response = await request(app).get('/api/weather');
    expect(response.statusCode).toBe(200);
    expect(response.body).toHaveProperty('location');
    expect(response.body.location).toBe('New York');
  });
});