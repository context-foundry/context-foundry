import { describe, test, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ProblemDisplay from '../../src/components/ProblemDisplay';
import AnswerInput from '../../src/components/AnswerInput';
import FeedbackDisplay from '../../src/components/FeedbackDisplay';
import ScoreBoard from '../../src/components/ScoreBoard';

describe('Accessibility Tests', () => {
  describe('ProblemDisplay', () => {
    test('has descriptive aria-label for addition', () => {
      render(<ProblemDisplay operation="addition" operand1={5} operand2={3} />);
      expect(screen.getByLabelText(/Math problem: 5 plus 3 equals what?/i)).toBeInTheDocument();
    });

    test('has descriptive aria-label for subtraction', () => {
      render(<ProblemDisplay operation="subtraction" operand1={10} operand2={4} />);
      expect(screen.getByLabelText(/Math problem: 10 minus 4 equals what?/i)).toBeInTheDocument();
    });

    test('has descriptive aria-label for multiplication', () => {
      render(<ProblemDisplay operation="multiplication" operand1={3} operand2={4} />);
      expect(screen.getByLabelText(/Math problem: 3 times 4 equals what?/i)).toBeInTheDocument();
    });

    test('displays correct operation symbols', () => {
      const { container, rerender } = render(
        <ProblemDisplay operation="addition" operand1={5} operand2={3} />
      );
      expect(container.textContent).toContain('+');

      rerender(<ProblemDisplay operation="subtraction" operand1={5} operand2={3} />);
      expect(container.textContent).toContain('-');

      rerender(<ProblemDisplay operation="multiplication" operand1={5} operand2={3} />);
      expect(container.textContent).toContain('×');
    });
  });

  describe('AnswerInput', () => {
    test('has proper label association', () => {
      const handleSubmit = vi.fn();
      render(<AnswerInput onSubmit={handleSubmit} disabled={false} />);

      const input = screen.getByLabelText(/Your answer/i);
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute('type', 'number');
    });

    test('supports keyboard navigation (Enter key)', () => {
      const handleSubmit = vi.fn();
      render(<AnswerInput onSubmit={handleSubmit} disabled={false} />);

      const input = screen.getByLabelText(/Your answer/i);

      fireEvent.change(input, { target: { value: '8' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(handleSubmit).toHaveBeenCalledWith('8');
    });

    test('button has descriptive aria-label', () => {
      const handleSubmit = vi.fn();
      render(<AnswerInput onSubmit={handleSubmit} disabled={false} />);

      const button = screen.getByLabelText(/Check your answer/i);
      expect(button).toBeInTheDocument();
    });

    test('disables input and button when disabled prop is true', () => {
      const handleSubmit = vi.fn();
      render(<AnswerInput onSubmit={handleSubmit} disabled={true} />);

      const input = screen.getByLabelText(/Your answer/i);
      const button = screen.getByLabelText(/Check your answer/i);

      expect(input).toBeDisabled();
      expect(button).toBeDisabled();
    });

    test('button is disabled when answer is empty', () => {
      const handleSubmit = vi.fn();
      render(<AnswerInput onSubmit={handleSubmit} disabled={false} />);

      const button = screen.getByLabelText(/Check your answer/i);
      expect(button).toBeDisabled();
    });

    test('button is enabled when answer is provided', () => {
      const handleSubmit = vi.fn();
      render(<AnswerInput onSubmit={handleSubmit} disabled={false} />);

      const input = screen.getByLabelText(/Your answer/i);
      const button = screen.getByLabelText(/Check your answer/i);

      fireEvent.change(input, { target: { value: '5' } });

      expect(button).not.toBeDisabled();
    });
  });

  describe('FeedbackDisplay', () => {
    test('announces to screen readers with role="alert"', () => {
      render(<FeedbackDisplay isCorrect={true} show={true} message="Great job! 🎉" />);

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
    });

    test('does not render when show is false', () => {
      const { container } = render(
        <FeedbackDisplay isCorrect={true} show={false} message="Great job! 🎉" />
      );

      expect(container.firstChild).toBeNull();
    });

    test('displays correct message content', () => {
      render(<FeedbackDisplay isCorrect={true} show={true} message="Perfect! 🍌" />);

      expect(screen.getByText(/Perfect! 🍌/i)).toBeInTheDocument();
    });
  });

  describe('ScoreBoard', () => {
    test('displays score information', () => {
      render(<ScoreBoard score={5} totalAttempts={10} streak={3} />);

      expect(screen.getByText('SCORE')).toBeInTheDocument();
      expect(screen.getByText('5 / 10')).toBeInTheDocument();
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    test('displays streak when greater than 0', () => {
      render(<ScoreBoard score={3} totalAttempts={5} streak={3} />);

      expect(screen.getByText('STREAK')).toBeInTheDocument();
      expect(screen.getByText(/3/)).toBeInTheDocument();
    });

    test('shows fire emoji when streak is 3 or more', () => {
      const { container, rerender } = render(
        <ScoreBoard score={3} totalAttempts={3} streak={3} />
      );

      expect(container.textContent).toContain('🔥');

      rerender(<ScoreBoard score={2} totalAttempts={2} streak={2} />);
      expect(container.textContent).not.toContain('🔥');
    });

    test('handles zero attempts correctly', () => {
      render(<ScoreBoard score={0} totalAttempts={0} streak={0} />);

      expect(screen.getByText('0 / 0')).toBeInTheDocument();
      expect(screen.getByText('0%')).toBeInTheDocument();
    });
  });

  describe('Touch Targets', () => {
    test('answer input button has minimum 60px height', () => {
      const handleSubmit = vi.fn();
      render(<AnswerInput onSubmit={handleSubmit} disabled={false} />);

      const button = screen.getByLabelText(/Check your answer/i);
      const styles = window.getComputedStyle(button);

      // Button has minHeight: 60px in inline styles
      expect(button).toHaveStyle({ minHeight: '60px' });
    });
  });
});
