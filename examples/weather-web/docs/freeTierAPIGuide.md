# Free Tier Weather API Guide

## Overview
This guide documents the WeatherAPI.com free tier requirements and limitations for the weather-web application migration from premium to free tier.

## Free Tier Specifications

### Base Configuration
- **Base URL**: `https://api.weatherapi.com/v1` (remove `/premium`)
- **API Key**: Same format, but registered for free tier
- **Monthly Limit**: 1,000,000 requests
- **Rate Limit**: 3 requests/second
- **Forecast Limit**: 3 days maximum

### Available Endpoints

#### ✅ Current Weather - `/current.json`