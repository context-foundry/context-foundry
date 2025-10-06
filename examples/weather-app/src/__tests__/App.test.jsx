import { render, screen } from '@testing-library/react';
import App from '../App';

test('renders Weather App title', () => {
  render(<App />);
  const heading = screen.getByText(/Weather App/i);
  expect(heading).toBeInTheDocument();
});