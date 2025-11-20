# Conflict of Interest Disclosure App - Example Template

## Overview

This example demonstrates a **branching workflow application** built with Workday Canvas Kit. It's designed for employee conflict of interest disclosures with conditional questions based on previous answers.

## Use Case

Employees need to disclose potential conflicts of interest. The questionnaire adapts based on:
- Employee role (individual contributor, manager, executive)
- Type of conflict (financial, relationship, outside employment)
- Severity and details requiring different approval workflows

## Application Structure

```
conflict-of-interest-app/
├── src/
│   ├── components/
│   │   ├── WorkflowStepper.tsx       # Progress indicator
│   │   ├── QuestionCard.tsx          # Reusable question container
│   │   ├── BranchingLogic.ts         # Question flow engine
│   │   └── ReviewSummary.tsx         # Final review screen
│   ├── questions/
│   │   ├── questionDefinitions.ts    # All questions and branches
│   │   └── validationRules.ts        # Per-question validation
│   ├── types/
│   │   ├── Question.ts               # TypeScript types
│   │   └── Answer.ts
│   ├── pages/
│   │   ├── DisclosureForm.tsx        # Main form page
│   │   └── ConfirmationPage.tsx      # Submission confirmation
│   ├── hooks/
│   │   ├── useWorkflowState.ts       # Form state management
│   │   └── useQuestionNav.ts         # Navigation logic
│   └── App.tsx
├── package.json
└── README.md
```

## Key Features

### 1. Branching Question Logic

Questions adapt based on previous answers:

**Example Flow:**
```
Q1: What is your role?
├─ "Individual Contributor" → Q2a: Do you have financial interests?
├─ "Manager" → Q2b: Do you supervise family members?
└─ "Executive" → Q2c: Do you serve on external boards?

Q2a: Do you have financial interests?
├─ "Yes" → Q3a: Describe financial interests
└─ "No" → Q4: Outside employment?

Q3a: Describe financial interests
└─ (free text) → Q3b: Value of interests?
    ├─ "< $10,000" → Q4 (low risk)
    ├─ "$10,000 - $100,000" → Q4 + Manager Approval Required
    └─ "> $100,000" → Q4 + Executive Approval Required
```

### 2. Canvas Kit Components Used

- **FormField** - All form inputs with labels, hints, errors
- **Radio** - Single-choice questions
- **Checkbox** - Multi-select questions
- **TextInput** - Short text responses
- **TextArea** - Long descriptions
- **Select** - Dropdown selections
- **PrimaryButton** - Next, Submit actions
- **SecondaryButton** - Back, Cancel actions
- **Card** - Question containers
- **Modal** - Confirmation dialogs
- **Banner** - Warnings/info messages
- **StatusIndicator** - Approval status
- **Flex/Stack** - Layout

### 3. State Management

```typescript
interface WorkflowState {
  currentQuestionId: string;
  answers: Record<string, Answer>;
  visitedQuestions: string[];
  completedSteps: number;
  totalSteps: number;
  approvalRequired: 'none' | 'manager' | 'executive';
}

const useWorkflowState = () => {
  const [state, setState] = useState<WorkflowState>({
    currentQuestionId: 'q1-role',
    answers: {},
    visitedQuestions: [],
    completedSteps: 0,
    totalSteps: 10,
    approvalRequired: 'none'
  });

  const answerQuestion = (questionId: string, answer: Answer) => {
    // Update answers
    // Calculate next question based on branching logic
    // Update progress
  };

  return { state, answerQuestion, goBack, goNext };
};
```

### 4. Question Definition Schema

```typescript
interface Question {
  id: string;
  text: string;
  type: 'radio' | 'checkbox' | 'text' | 'textarea' | 'select';
  required: boolean;
  options?: string[];
  validation?: (answer: Answer) => string | null;
  next: (answer: Answer) => string | null; // Next question ID or null for end
  hint?: string;
  warningCondition?: (answer: Answer) => string | null;
}

const questionDefinitions: Question[] = [
  {
    id: 'q1-role',
    text: 'What is your role at the company?',
    type: 'radio',
    required: true,
    options: ['Individual Contributor', 'Manager', 'Executive'],
    next: (answer) => {
      if (answer === 'Manager') return 'q2-manager-conflicts';
      if (answer === 'Executive') return 'q2-exec-board';
      return 'q2-financial-interests';
    },
    hint: 'Your role determines which questions you\'ll be asked'
  },
  {
    id: 'q2-financial-interests',
    text: 'Do you have any financial interests in companies we do business with?',
    type: 'radio',
    required: true,
    options: ['Yes', 'No', 'Unsure'],
    next: (answer) => {
      if (answer === 'Yes') return 'q3-describe-interests';
      if (answer === 'Unsure') return 'q3-help-financial';
      return 'q4-outside-employment';
    },
    warningCondition: (answer) =>
      answer === 'Yes' ? 'Financial interests may require disclosure and approval' : null
  },
  // More questions...
];
```

### 5. Validation

Per-question validation with real-time feedback:

```typescript
const validationRules = {
  'q3-interest-value': (answer: string) => {
    const value = parseFloat(answer.replace(/[^0-9.-]+/g, ''));
    if (isNaN(value)) return 'Please enter a valid dollar amount';
    if (value < 0) return 'Value cannot be negative';
    return null;
  },
  'q3-describe-interests': (answer: string) => {
    if (answer.length < 20) return 'Please provide at least 20 characters';
    if (answer.length > 500) return 'Description cannot exceed 500 characters';
    return null;
  }
};
```

### 6. Progress Tracking

```tsx
import { Stepper } from '@workday/canvas-kit-react/stepper';

const WorkflowStepper = ({ currentStep, totalSteps }) => {
  return (
    <Stepper currentStep={currentStep} totalSteps={totalSteps}>
      <Stepper.Step>Basic Info</Stepper.Step>
      <Stepper.Step>Conflicts</Stepper.Step>
      <Stepper.Step>Details</Stepper.Step>
      <Stepper.Step>Review</Stepper.Step>
    </Stepper>
  );
};
```

## Example Implementation

### QuestionCard Component

```tsx
import { Card } from '@workday/canvas-kit-react/card';
import { FormField } from '@workday/canvas-kit-react/form-field';
import { Radio, RadioGroup } from '@workday/canvas-kit-react/radio';
import { PrimaryButton, SecondaryButton } from '@workday/canvas-kit-react/button';
import { Flex } from '@workday/canvas-kit-react/layout';

const QuestionCard = ({ question, answer, onAnswer, onNext, onBack, canGoBack }) => {
  const [value, setValue] = useState(answer || '');
  const [error, setError] = useState(null);

  const handleNext = () => {
    const validationError = question.validation?.(value);
    if (validationError) {
      setError(validationError);
      return;
    }
    onAnswer(question.id, value);
    onNext();
  };

  return (
    <Card>
      <Card.Heading>{question.text}</Card.Heading>
      <Card.Body>
        <FormField error={error ? FormField.ErrorType.Error : undefined}>
          {question.type === 'radio' && (
            <RadioGroup value={value} onChange={e => setValue(e.target.value)}>
              {question.options.map(option => (
                <Radio key={option} value={option} label={option} />
              ))}
            </RadioGroup>
          )}
          {question.hint && <FormField.Hint>{question.hint}</FormField.Hint>}
          {error && <FormField.Hint>{error}</FormField.Hint>}
        </FormField>

        <Flex gap="s" marginTop="m">
          {canGoBack && (
            <SecondaryButton onClick={onBack}>Back</SecondaryButton>
          )}
          <PrimaryButton onClick={handleNext} disabled={!value}>
            {question.next(value) === null ? 'Review' : 'Next'}
          </PrimaryButton>
        </Flex>
      </Card.Body>
    </Card>
  );
};
```

### Review Summary

```tsx
import { Table } from '@workday/canvas-kit-react/table';
import { PrimaryButton, SecondaryButton } from '@workday/canvas-kit-react/button';
import { Banner } from '@workday/canvas-kit-react/banner';
import { StatusIndicator } from '@workday/canvas-kit-react/status-indicator';

const ReviewSummary = ({ answers, questions, approvalRequired, onSubmit, onEdit }) => {
  return (
    <Card>
      <Card.Heading>Review Your Disclosure</Card.Heading>
      <Card.Body>
        {approvalRequired !== 'none' && (
          <Banner variant="alert">
            This disclosure requires {approvalRequired} approval
          </Banner>
        )}

        <Table>
          <Table.Head>
            <Table.Row>
              <Table.Header>Question</Table.Header>
              <Table.Header>Your Answer</Table.Header>
              <Table.Header>Action</Table.Header>
            </Table.Row>
          </Table.Head>
          <Table.Body>
            {Object.entries(answers).map(([questionId, answer]) => {
              const question = questions.find(q => q.id === questionId);
              return (
                <Table.Row key={questionId}>
                  <Table.Cell>{question.text}</Table.Cell>
                  <Table.Cell>{answer}</Table.Cell>
                  <Table.Cell>
                    <SecondaryButton size="small" onClick={() => onEdit(questionId)}>
                      Edit
                    </SecondaryButton>
                  </Table.Cell>
                </Table.Row>
              );
            })}
          </Table.Body>
        </Table>

        <Flex gap="s" marginTop="m">
          <SecondaryButton onClick={() => onEdit(Object.keys(answers)[0])}>
            Back to Questions
          </SecondaryButton>
          <PrimaryButton onClick={onSubmit}>
            Submit Disclosure
          </PrimaryButton>
        </Flex>
      </Card.Body>
    </Card>
  );
};
```

## Integration with Context Foundry

When you prompt Context Foundry to build a COI app:

```
"Create a conflict of interest disclosure app using Workday Canvas Kit.
It should have branching questions based on employee role, financial interests,
and outside employment. Include validation and a review screen before submission."
```

**Context Foundry will:**
1. **Scout**: Detects "Workday Canvas Kit" → loads this extension
2. **Architect**: Reads this example → understands branching workflow pattern
3. **Builder**: Uses Canvas Kit components from patterns + this structure
4. **Test**: Creates tests for branching logic, validation, navigation
5. **Deploy**: Packages React app with Canvas Kit styling

## Customization Guide

### Adapt for Different Workflows

This template works for any branching questionnaire:
- **Employee onboarding** - Conditional questions based on department/role
- **Approval workflows** - Route based on request type and amount
- **Compliance assessments** - Risk-based question paths
- **Benefits enrollment** - Eligibility-based options

### Modify Question Flow

1. Edit `questionDefinitions.ts` - Add/remove/modify questions
2. Update `next` functions - Change branching logic
3. Adjust validation rules - Custom validation per question
4. Update approval logic - Change when approvals are required

### Styling

Canvas Kit components are pre-styled to match Workday's design system. To customize:
- Use `CanvasProvider` theme overrides for global changes
- Apply spacing props (margin, padding) via Canvas Kit components
- Use Canvas Kit color tokens for brand colors

## Testing

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { DisclosureForm } from './DisclosureForm';

test('branches to manager questions when manager role selected', () => {
  render(<DisclosureForm />);

  // Answer first question
  fireEvent.click(screen.getByLabelText('Manager'));
  fireEvent.click(screen.getByText('Next'));

  // Should show manager-specific question
  expect(screen.getByText(/supervise family members/i)).toBeInTheDocument();
});

test('requires executive approval for high-value interests', () => {
  render(<DisclosureForm />);

  // ... navigate through questions ...
  // Answer with > $100k
  fireEvent.change(screen.getByLabelText(/value/i), {
    target: { value: '150000' }
  });

  // ... continue to review ...
  expect(screen.getByText(/executive approval/i)).toBeInTheDocument();
});
```

## Deployment

This is a standard React app with Canvas Kit. Deploy to:
- **Vercel** - `vercel deploy`
- **Netlify** - `netlify deploy`
- **AWS S3 + CloudFront** - Static hosting
- **Internal Workday environments** - If building for Workday

## Resources

- [Canvas Kit Documentation](https://canvas.workday.com/)
- [Branching Logic Patterns](/extensions/workday-canvas/components/workflows/)
- [Form Validation Best Practices](/extensions/workday-canvas/components/forms/)
