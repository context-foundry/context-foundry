# Workflow Patterns - Branching Question Flows

## Overview

This directory contains reusable patterns for implementing branching workflows with Canvas Kit components. These patterns are commonly used for:

- Conditional questionnaires
- Multi-step forms with dynamic paths
- Approval workflows with routing logic
- Compliance assessments
- Onboarding flows

## Pattern: Question State Machine

### Core Concept

Each question can lead to different next questions based on the answer. This creates a directed graph of questions rather than a linear sequence.

```
          ┌─────────┐
          │  Start  │
          └────┬────┘
               │
          ┌────▼────┐
          │   Q1    │ "What is your role?"
          └────┬────┘
               │
        ┌──────┼──────┐
        │      │      │
     ┌──▼──┐ ┌▼──┐ ┌─▼──┐
     │ Q2a │ │Q2b│ │Q2c │
     └──┬──┘ └┬──┘ └─┬──┘
        │     │      │
        └─────┼──────┘
              │
          ┌───▼───┐
          │  Q3   │
          └───┬───┘
              │
          ┌───▼───┐
          │ Review│
          └───────┘
```

### Implementation

#### 1. Question Definition Type

```typescript
interface Question {
  id: string;
  text: string;
  type: 'radio' | 'checkbox' | 'text' | 'textarea' | 'select' | 'number';
  required: boolean;
  options?: string[]; // For radio, checkbox, select
  validation?: (answer: any) => string | null;
  next: (answer: any, allAnswers: Record<string, any>) => string | null;
  hint?: string;
  warningCondition?: (answer: any) => string | null;
  metadata?: {
    category?: string;
    riskLevel?: 'low' | 'medium' | 'high';
    requiresApproval?: boolean;
  };
}
```

#### 2. Workflow State Management

```typescript
import { useState, useCallback } from 'react';

interface WorkflowState {
  currentQuestionId: string;
  answers: Record<string, any>;
  history: string[]; // For back navigation
  completionPercentage: number;
}

export const useWorkflowState = (initialQuestionId: string) => {
  const [state, setState] = useState<WorkflowState>({
    currentQuestionId: initialQuestionId,
    answers: {},
    history: [],
    completionPercentage: 0
  });

  const answerQuestion = useCallback((questionId: string, answer: any) => {
    setState(prev => ({
      ...prev,
      answers: { ...prev.answers, [questionId]: answer },
      history: [...prev.history, questionId]
    }));
  }, []);

  const navigateNext = useCallback((nextQuestionId: string | null) => {
    if (nextQuestionId === null) {
      // Workflow complete
      setState(prev => ({ ...prev, currentQuestionId: 'REVIEW' }));
    } else {
      setState(prev => ({ ...prev, currentQuestionId: nextQuestionId }));
    }
  }, []);

  const navigateBack = useCallback(() => {
    setState(prev => {
      const newHistory = [...prev.history];
      const previousQuestionId = newHistory.pop();
      return {
        ...prev,
        currentQuestionId: previousQuestionId || prev.currentQuestionId,
        history: newHistory
      };
    });
  }, []);

  return { state, answerQuestion, navigateNext, navigateBack };
};
```

#### 3. Question Renderer

```tsx
import { Card } from '@workday/canvas-kit-react/card';
import { FormField } from '@workday/canvas-kit-react/form-field';
import { Radio, RadioGroup } from '@workday/canvas-kit-react/radio';
import { Checkbox } from '@workday/canvas-kit-react/checkbox';
import { TextInput } from '@workday/canvas-kit-react/text-input';
import { TextArea } from '@workday/canvas-kit-react/text-area';
import { Select } from '@workday/canvas-kit-react/select';
import { PrimaryButton, SecondaryButton } from '@workday/canvas-kit-react/button';
import { Flex, Stack } from '@workday/canvas-kit-react/layout';
import { Banner } from '@workday/canvas-kit-react/banner';

const QuestionRenderer = ({
  question,
  currentAnswer,
  onAnswer,
  onNext,
  onBack,
  canGoBack,
  allAnswers
}) => {
  const [value, setValue] = useState(currentAnswer || '');
  const [error, setError] = useState(null);
  const [warning, setWarning] = useState(null);

  const handleChange = (newValue) => {
    setValue(newValue);
    setError(null);

    // Check for warnings
    if (question.warningCondition) {
      const warningMsg = question.warningCondition(newValue);
      setWarning(warningMsg);
    }
  };

  const handleNext = () => {
    // Validate
    if (question.required && !value) {
      setError('This field is required');
      return;
    }

    if (question.validation) {
      const validationError = question.validation(value);
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    // Save answer
    onAnswer(question.id, value);

    // Calculate next question
    const nextQuestionId = question.next(value, allAnswers);
    onNext(nextQuestionId);
  };

  const renderInput = () => {
    switch (question.type) {
      case 'radio':
        return (
          <RadioGroup value={value} onChange={e => handleChange(e.target.value)}>
            <Stack spacing="s">
              {question.options?.map(option => (
                <Radio key={option} value={option} label={option} />
              ))}
            </Stack>
          </RadioGroup>
        );

      case 'checkbox':
        return (
          <Stack spacing="s">
            {question.options?.map(option => (
              <Checkbox
                key={option}
                checked={value.includes?.(option)}
                onChange={e => {
                  const newValue = e.target.checked
                    ? [...(value || []), option]
                    : value.filter(v => v !== option);
                  handleChange(newValue);
                }}
                label={option}
              />
            ))}
          </Stack>
        );

      case 'text':
        return (
          <TextInput
            value={value}
            onChange={e => handleChange(e.target.value)}
            placeholder={question.hint}
          />
        );

      case 'textarea':
        return (
          <TextArea
            value={value}
            onChange={e => handleChange(e.target.value)}
            placeholder={question.hint}
          />
        );

      case 'select':
        return (
          <Select value={value} onChange={e => handleChange(e.target.value)}>
            <option value="">Select an option...</option>
            {question.options?.map(option => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </Select>
        );

      case 'number':
        return (
          <TextInput
            type="number"
            value={value}
            onChange={e => handleChange(e.target.value)}
            placeholder={question.hint}
          />
        );

      default:
        return null;
    }
  };

  return (
    <Card>
      <Card.Heading>{question.text}</Card.Heading>
      <Card.Body>
        <Stack spacing="m">
          {warning && (
            <Banner variant="alert">{warning}</Banner>
          )}

          <FormField error={error ? FormField.ErrorType.Error : undefined}>
            {renderInput()}
            {question.hint && !error && (
              <FormField.Hint>{question.hint}</FormField.Hint>
            )}
            {error && <FormField.Hint>{error}</FormField.Hint>}
          </FormField>

          <Flex gap="s">
            {canGoBack && (
              <SecondaryButton onClick={onBack}>
                Back
              </SecondaryButton>
            )}
            <PrimaryButton onClick={handleNext} disabled={!value && question.required}>
              {question.next(value, allAnswers) === null ? 'Review Answers' : 'Next'}
            </PrimaryButton>
          </Flex>
        </Stack>
      </Card.Body>
    </Card>
  );
};
```

## Pattern: Conditional Routing

### Simple Branching

```typescript
const questions: Question[] = [
  {
    id: 'q1',
    text: 'Are you a US citizen?',
    type: 'radio',
    required: true,
    options: ['Yes', 'No'],
    next: (answer) => answer === 'Yes' ? 'q2-us' : 'q2-intl'
  }
];
```

### Complex Multi-Factor Routing

```typescript
const questions: Question[] = [
  {
    id: 'q3-interest-value',
    text: 'What is the approximate value of your financial interest?',
    type: 'select',
    required: true,
    options: [
      'Less than $10,000',
      '$10,000 - $50,000',
      '$50,000 - $100,000',
      'More than $100,000'
    ],
    next: (answer, allAnswers) => {
      // Multi-factor logic
      const role = allAnswers['q1-role'];
      const hasOtherConflicts = allAnswers['q2-other-conflicts'] === 'Yes';

      if (answer === 'More than $100,000') {
        return 'q4-exec-review-required';
      } else if (answer === '$50,000 - $100,000' && role === 'Manager') {
        return 'q4-manager-review';
      } else if (hasOtherConflicts) {
        return 'q4-additional-disclosure';
      } else {
        return 'q5-outside-employment';
      }
    },
    metadata: {
      requiresApproval: true
    }
  }
];
```

## Pattern: Progress Tracking

### Linear Progress Estimation

```typescript
const calculateProgress = (
  currentQuestionId: string,
  questions: Question[],
  answers: Record<string, any>
): number => {
  const totalQuestions = questions.length;
  const answeredCount = Object.keys(answers).length;
  return Math.round((answeredCount / totalQuestions) * 100);
};
```

### Graph-Based Progress (More Accurate)

```typescript
const calculateProgress = (
  currentQuestionId: string,
  questions: Question[],
  answers: Record<string, any>
): number => {
  // Simulate the path based on current answers
  let questionId = questions[0].id;
  let pathLength = 0;
  let completedLength = 0;

  while (questionId !== null) {
    pathLength++;
    const question = questions.find(q => q.id === questionId);
    const answer = answers[questionId];

    if (answer !== undefined) {
      completedLength++;
    } else if (questionId === currentQuestionId) {
      break;
    }

    questionId = question.next(answer, answers);
  }

  return Math.round((completedLength / pathLength) * 100);
};
```

## Pattern: Answer Persistence

### Local Storage

```typescript
const usePersistedWorkflow = (workflowId: string) => {
  const storageKey = `workflow-${workflowId}`;

  const loadState = (): WorkflowState | null => {
    const saved = localStorage.getItem(storageKey);
    return saved ? JSON.parse(saved) : null;
  };

  const saveState = (state: WorkflowState) => {
    localStorage.setItem(storageKey, JSON.stringify(state));
  };

  const clearState = () => {
    localStorage.removeItem(storageKey);
  };

  return { loadState, saveState, clearState };
};
```

### API Persistence

```typescript
const useApiPersistedWorkflow = (workflowId: string, userId: string) => {
  const saveProgress = async (answers: Record<string, any>) => {
    await fetch(`/api/workflows/${workflowId}/users/${userId}/progress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers, lastUpdated: new Date() })
    });
  };

  const loadProgress = async () => {
    const response = await fetch(`/api/workflows/${workflowId}/users/${userId}/progress`);
    return response.json();
  };

  return { saveProgress, loadProgress };
};
```

## Testing Branching Logic

```typescript
import { renderHook, act } from '@testing-library/react-hooks';
import { useWorkflowState } from './useWorkflowState';

describe('Workflow branching', () => {
  test('navigates to manager questions when manager role selected', () => {
    const { result } = renderHook(() => useWorkflowState('q1-role'));

    act(() => {
      result.current.answerQuestion('q1-role', 'Manager');
      result.current.navigateNext('q2-manager-conflicts');
    });

    expect(result.current.state.currentQuestionId).toBe('q2-manager-conflicts');
    expect(result.current.state.answers['q1-role']).toBe('Manager');
  });

  test('can navigate back through history', () => {
    const { result } = renderHook(() => useWorkflowState('q1'));

    act(() => {
      result.current.answerQuestion('q1', 'Yes');
      result.current.navigateNext('q2');
      result.current.answerQuestion('q2', 'No');
      result.current.navigateNext('q3');
    });

    expect(result.current.state.currentQuestionId).toBe('q3');

    act(() => {
      result.current.navigateBack();
    });

    expect(result.current.state.currentQuestionId).toBe('q2');
  });
});
```

## Best Practices

1. **Keep branching logic in question definitions** - Don't scatter routing logic across components
2. **Validate before routing** - Always validate the current answer before calculating next question
3. **Support back navigation** - Users should be able to review/change previous answers
4. **Show progress** - Give users a sense of how far through the workflow they are
5. **Persist state** - Save progress so users can resume later
6. **Test all paths** - Write tests for each possible route through the workflow
7. **Handle edge cases** - What happens if user refreshes mid-flow? If they answer inconsistently?

## Common Pitfalls

- ❌ Hardcoding question order (use dynamic next() functions)
- ❌ Not validating before routing (can lead to invalid states)
- ❌ Forgetting to handle null next (end of workflow)
- ❌ Not persisting state (user loses progress on refresh)
- ❌ Complex nested conditionals (extract to helper functions)
- ❌ Not testing all branches (critical bugs in edge cases)
