import React from 'react';
import 'bootstrap/dist/css/bootstrap.min.css';

/**
 * WeatherCard component displays weather information.
 * 
 * @param {Object} props - The properties object.
 * @param {string} props.city - The name of the city.
 * @param {string} props.temperature - The temperature value.
 * @param {string} props.condition - The weather condition.
 * @param {string} props.icon - The URL for the weather icon.
 * @returns {JSX.Element} The WeatherCard component.
 */
const WeatherCard = ({ city, temperature, condition, icon }) => {
    return (
        <div className="card mb-3" style={{maxWidth: "540px"}}>
            <div className="row g-0">
                <div className="col-md-4">
                    <img src={icon} className="img-fluid rounded-start" alt="Weather Icon" />
                </div>
                <div className="col-md-8">
                    <div className="card-body">
                        <h5 className="card-title">{city}</h5>
                        <p className="card-text">{temperature} °C</p>
                        <p className="card-text"><small className="text-muted">{condition}</small></p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default WeatherCard;