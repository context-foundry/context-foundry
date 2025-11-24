# 🦍 Gorilla Math Game

An educational web game for 2nd graders to practice addition, subtraction, and multiplication with instant feedback and a fun gorilla theme!

![Gorilla Math Game](public/gorilla-happy.svg)

## 🎯 Educational Goals

- **Target Age**: 2nd grade (ages 7-8)
- **Skills**: Addition (0-20), Subtraction (0-20), Multiplication (1-5)
- **Common Core Alignment**: 2.OA.B.2 (fluency with addition/subtraction within 20)

## ✨ Features

- 🎲 Random problem generation with age-appropriate difficulty
- ✅ Immediate feedback with encouraging messages
- 📊 Score tracking with streak counter
- 🦍 Animated gorilla mascot that reacts to answers
- ♿ Fully keyboard accessible (Tab navigation, Enter to submit)
- 📱 Touch-friendly on tablets with large buttons (60px+ height)
- 🎨 Colorful, kid-friendly design with high contrast
- 🔊 Optional sound effects for success/failure

## 🚀 Quick Start

### Installation

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### Browser Requirements

- Chrome 90+ (2021 or newer)
- Safari 14+
- Firefox 88+

### Production Build

```bash
npm run build   # Build production version to dist/
npm run preview # Preview production build locally
```

### Deployment to GitHub Pages

```bash
npm run deploy  # Build and deploy to GitHub Pages
```

## 🎮 How to Play

1. Click "Start Game" on the welcome screen
2. Solve the math problem shown (addition, subtraction, or multiplication)
3. Type your answer in the input field
4. Press Enter or click "Check Answer"
5. See if you got it right! 🎉
6. Try to build a streak of correct answers to see the fire emoji! 🔥
7. Press ESC or click "Back to Start" to reset the game

## 🧪 Testing

### Unit & Component Tests

```bash
npm run test        # Run tests in watch mode
npm run test:run    # Run tests once
npm run test:ui     # Run tests with UI
```

### End-to-End Tests

```bash
npm run test:e2e       # Run E2E tests
npm run test:e2e:ui    # Run E2E tests with UI
```

### Manual Testing Checklist

Before deploying, verify:

- [ ] Open in Chrome, Safari, Firefox - no console errors
- [ ] Click "Start Game" → math problem displays
- [ ] Type answer → press Enter → feedback shows
- [ ] Correct answer → score increases, gorilla celebrates
- [ ] Incorrect answer → friendly message, correct answer shown
- [ ] Wait 2 seconds → next problem automatically appears
- [ ] Test 5+ problems → verify variety (addition, subtraction, multiplication)
- [ ] Reset game → state clears, returns to welcome screen
- [ ] Test on tablet (if available) → touch targets work
- [ ] Check accessibility: Tab key navigation works, labels present

## 📁 Project Structure

```
gorilla-math-game/
├── public/                   # Static assets
│   ├── gorilla-happy.svg     # Correct answer animation
│   ├── gorilla-thinking.svg  # Default state
│   └── gorilla-oops.svg      # Incorrect answer
├── src/
│   ├── components/           # React components
│   │   ├── GameContainer.jsx
│   │   ├── WelcomeScreen.jsx
│   │   ├── ProblemDisplay.jsx
│   │   ├── AnswerInput.jsx
│   │   ├── FeedbackDisplay.jsx
│   │   ├── ScoreBoard.jsx
│   │   └── GorillaCharacter.jsx
│   ├── hooks/
│   │   └── useGameState.js   # Game state management
│   ├── utils/
│   │   ├── problemGenerator.js
│   │   ├── constants.js
│   │   └── soundManager.js
│   ├── App.jsx               # Root component
│   ├── App.css               # Global styles + Tailwind
│   └── main.jsx              # Entry point
├── tests/
│   ├── unit/                 # Unit tests
│   ├── component/            # Component tests
│   └── e2e/                  # E2E tests
├── index.html                # HTML entry (ROOT location!)
├── vite.config.js
├── tailwind.config.js
├── vitest.config.js
├── playwright.config.js
└── package.json
```

## 🏗️ Architecture

### Component Hierarchy

```
App
├── WelcomeScreen (initial state)
└── GameContainer (active game)
    ├── ScoreBoard (fixed position)
    ├── GorillaCharacter (animated mascot)
    ├── ProblemDisplay (math problem)
    ├── AnswerInput (user input)
    └── FeedbackDisplay (conditional)
```

### State Management

Uses custom `useGameState` hook for centralized game logic:

- Problem generation with age-appropriate ranges
- Answer validation
- Score and streak tracking
- Automatic next problem generation after 2-second delay

### Problem Generation Rules

- **Addition**: Operands 0-20, results ≤ 25
- **Subtraction**: Operands 0-20, results ≥ 0 (no negatives!)
- **Multiplication**: Operands 1-5, results ≤ 25

## ♿ Accessibility

- ✅ **WCAG AA Compliant**: High contrast ratios (4.5:1 minimum)
- ✅ **Screen Reader Support**: ARIA labels and roles
- ✅ **Keyboard Navigation**: Full keyboard support (Tab, Enter, ESC)
- ✅ **Focus Indicators**: Visible focus outlines on all interactive elements
- ✅ **Large Touch Targets**: Minimum 44px for mobile/tablet use
- ✅ **Semantic HTML**: Proper use of `<button>`, `<label>`, `<input>` elements

### Accessibility Features by Component

- **ProblemDisplay**: `aria-label` announces problem ("5 plus 3 equals what?")
- **AnswerInput**: Proper `<label>` association, keyboard shortcuts
- **FeedbackDisplay**: `role="alert"` for screen reader announcements
- **ScoreBoard**: Clear labeling of score and streak information

## 🎨 Design System

### Colors

- **Backgrounds**: Gradient from yellow-100 to green-100 (welcome), blue-100 to purple-100 (game)
- **Operation Symbols**: Green (+), Red (-), Blue (×)
- **Feedback**: Green gradient (correct), Orange/Yellow gradient (incorrect)
- **Buttons**: Blue (primary), Gray (secondary)

### Typography

- **Problem Display**: 48px (3rem) on mobile, 56px (3.5rem) on desktop
- **Buttons**: 24px-32px bold
- **Body Text**: 18px minimum

### Animations

- **Feedback**: Fade-in with scale (0.3s)
- **Gorilla**: Bounce on correct, pulse on incorrect
- **Buttons**: Scale transform on hover (1.05)

## 🛠️ Technology Stack

- **Vite 7.x** - Fast dev server and build tool
- **React 19.x** - UI framework (JavaScript, no TypeScript)
- **Tailwind CSS 4.x** - Utility-first styling
- **Vitest** - Unit and component testing
- **React Testing Library** - Component testing with accessibility focus
- **Playwright** - E2E testing
- **gh-pages** - GitHub Pages deployment

## 📄 License

MIT

## 🙏 Credits

- Gorilla SVG graphics: Custom created for this project
- Built with [Vite](https://vitejs.dev) + [React](https://react.dev)
- Styled with [Tailwind CSS](https://tailwindcss.com)
- Icons and emojis: Native emoji support

## 🔗 Live Demo

[Play Gorilla Math Game](#) _(Deploy to GitHub Pages and add link here)_

## 🤝 Contributing

This is an educational project designed for 2nd graders. Contributions that enhance accessibility, add educational value, or improve the learning experience are welcome!

### Guidelines

- Maintain age-appropriate difficulty (2nd grade level)
- Keep the interface simple and colorful
- Ensure all features are accessible
- Add tests for new features
- Follow existing code style

## 📝 Development Notes

### Why Vite + React?

- **Fast**: <100ms dev server startup, instant HMR
- **Simple**: No complex configuration needed
- **Modern**: Uses latest web standards
- **Optimized**: Production builds are highly optimized

### Why No TypeScript?

- Reduces complexity for simple game logic
- Easier for beginners to understand and contribute
- Faster development for this use case

### Why Tailwind CSS?

- Rapid prototyping with utility classes
- Smaller bundle size than custom CSS for this project
- Built-in responsive design utilities
- Consistent design system

## 🐛 Known Issues

None currently! If you find a bug, please report it.

## 🚀 Future Enhancements

Potential features for future versions:

- [ ] Difficulty levels (Easy/Medium/Hard)
- [ ] Division problems for advanced students
- [ ] Timed challenge mode
- [ ] Multiplayer mode
- [ ] Progress tracking/analytics
- [ ] Customizable themes
- [ ] Additional mascot characters
- [ ] Sound effects toggle
- [ ] Print certificates for achievements

---

Made with ❤️ for young learners

**Perfect for:**
- Classroom use on tablets
- Homework practice
- Math centers
- Remote learning
- Homeschool math practice
