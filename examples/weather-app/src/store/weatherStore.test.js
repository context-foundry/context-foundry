import { render, screen } from '@testing-library/react';
import { WeatherProvider } from './weatherStore';
import App from '../App';

test('provides weather context', () => {
  render(
    <WeatherProvider>
      <App />
    </WeatherProvider>
  );

  expect(screen.getByText(/error/i)).toBeInTheDocument(); // Check for error component/message
});