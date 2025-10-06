/**
 * Geolocation functionality for weather-app
 * Provides methods to get the user's current location using Geolocation API
 */

export async function getUserLocation() {
    /**
     * Retrieves the user's current geographical location using the browser's Geolocation API.
     * Returns:
     * - A Promise that resolves to an object containing latitude and longitude coordinates.
     * - Throws an error if location is unavailable or the user denies permission.
     */
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            // Geolocation API unavailable
            reject(new Error("Geolocation is not supported by your browser."));
        }

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const { latitude, longitude } = position.coords;
                resolve({ latitude, longitude });
            },
            (error) => {
                // Handle errors from Geolocation API
                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        reject(new Error("User denied the request for Geolocation."));
                        break;
                    case error.POSITION_UNAVAILABLE:
                        reject(new Error("Location information is unavailable."));
                        break;
                    case error.TIMEOUT:
                        reject(new Error("The request to get user location timed out."));
                        break;
                    default:
                        reject(new Error("An unknown error occurred."));
                        break;
                }
            }
        );
    });
}

/**
 * Example usage:
 * getUserLocation()
 *    .then(location => console.log("User Location:", location))
 *    .catch(error => console.error("Error:", error));
 */