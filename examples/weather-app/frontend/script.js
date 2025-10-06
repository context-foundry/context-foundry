document.getElementById("weatherForm").addEventListener("submit", async (event) => {
    event.preventDefault();

    const cityInput = document.getElementById("cityInput").value;
    const resultDiv = document.getElementById("weatherResult");
    
    resultDiv.classList.add("hidden");
    resultDiv.innerHTML = "";

    try {
        const response = await fetch(`/api/weather?city=${encodeURIComponent(cityInput)}`);
        if (!response.ok) {
            throw new Error("Failed to fetch weather data");
        }

        const data = await response.json();
        if (data.error) {
            throw new Error(data.error);
        }

        document.getElementById("cityName").textContent = `Weather in ${data.city}`;
        document.getElementById("temperature").textContent = `Temperature: ${data.temperature}°C`;
        document.getElementById("description").textContent = `Condition: ${data.description}`;
        document.getElementById("icon").src = `http://openweathermap.org/img/w/${data.icon}.png`;

        resultDiv.classList.remove("hidden");
    } catch (error) {
        alert(error.message);
    }
});