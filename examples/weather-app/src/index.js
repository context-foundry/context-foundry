// Entry point for the app
import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css'; // TailwindCSS enabled file
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);