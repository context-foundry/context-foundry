import { render, screen } from '@testing-library/react';
import App from './App';

test('renders weather app title', () => {
  render(<App />);
  const titleElement = screen.getByText(/weather app/i);
  expect(titleElement).toBeInTheDocument();
});