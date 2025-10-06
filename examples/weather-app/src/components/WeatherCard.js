import React from 'react';
import styled from 'styled-components';

const Card = styled.div`
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 20px;
    margin: 10px;
    text-align: center;

    @media (max-width: 600px) {
        width: 80%;
    }
`;

const WeatherCard = ({ city, temperature, weather }) => {
    return (
        <Card>
            <h2>{city}</h2>
            <p>Temperature: {temperature}°C</p>
            <p>{weather}</p>
        </Card>
    );
};

export default WeatherCard;