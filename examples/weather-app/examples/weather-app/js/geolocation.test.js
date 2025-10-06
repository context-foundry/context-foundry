/**
 * Test cases for geolocation functionality
 */

import { getUserLocation } from './geolocation';

describe('Geolocation functionality', () => {
    test('Should resolve with latitude and longitude if Geolocation API succeeds', async () => {
        // Mock navigator.geolocation.getCurrentPosition for success case
        const mockSuccess = jest.fn((successCallback) => {
            successCallback({
                coords: {
                    latitude: 37.7749,
                    longitude: -122.4194,
                },
            });
        });

        Object.defineProperty(global.navigator, "geolocation", {
            value: {
                getCurrentPosition: mockSuccess,
            },
        });

        const location = await getUserLocation();
        expect(location).toEqual({ latitude: 37.7749, longitude: -122.4194 });
    });

    test('Should reject if Geolocation API fails with PERMISSION_DENIED', async () => {
        // Mock navigator.geolocation.getCurrentPosition for error case
        const mockError = jest.fn((_, errorCallback) => {
            errorCallback({ code: 1 });
        });

        Object.defineProperty(global.navigator, "geolocation", {
            value: {
                getCurrentPosition: mockError,
            },
        });

        await expect(getUserLocation()).rejects.toThrow("User denied the request for Geolocation.");
    });

    test('Should reject if Geolocation API fails with POSITION_UNAVAILABLE', async () => {
        const mockError = jest.fn((_, errorCallback) => {
            errorCallback({ code: 2 });
        });

        Object.defineProperty(global.navigator, "geolocation", {
            value: {
                getCurrentPosition: mockError,
            },
        });

        await expect(getUserLocation()).rejects.toThrow("Location information is unavailable.");
    });

    test('Should reject if Geolocation API fails with TIMEOUT', async () => {
        const mockError = jest.fn((_, errorCallback) => {
            errorCallback({ code: 3 });
        });

        Object.defineProperty(global.navigator, "geolocation", {
            value: {
                getCurrentPosition: mockError,
            },
        });

        await expect(getUserLocation()).rejects.toThrow("The request to get user location timed out.");
    });

    test('Should reject if Geolocation API is unavailable', async () => {
        Object.defineProperty(global.navigator, "geolocation", {
            value: undefined,
        });

        await expect(getUserLocation()).rejects.toThrow("Geolocation is not supported by your browser.");
    });
});