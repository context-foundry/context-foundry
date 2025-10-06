import React from 'react';
import styled from 'styled-components';

const ForecastContainer = styled.div`
    display: flex;
    justify-content: space-around;
    flex-wrap: wrap;

    @media (max-width: 600px) {
        flex-direction: column;
        align-items: center;
    }
`;

const ForecastCard = styled.div`
    background: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 1rem;
    margin: 1rem;
    text-align: center;
    flex: 1 1 calc(20% - 2rem); /* 5 items per row with some margin */

    @media (max-width: 600px) {
        flex: 1 1 80%;
    }
`;

const Forecast = ({ forecasts }) => {
    return (
        <ForecastContainer>
            {forecasts.map((forecast) => (
                <ForecastCard key={forecast.date}>
                    <h3>{forecast.date}</h3>
                    <p>{forecast.weather}</p>
                    <p>Temp: {forecast.temperature}°C</p>
                </ForecastCard>
            ))}
        </ForecastContainer>
    );
};

export default Forecast;