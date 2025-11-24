# 🦍 Gorilla Math Game

An educational web game for 2nd graders to practice addition, subtraction, and multiplication through an engaging gorilla theme!

## 🎯 Educational Target

- **Grade Level**: 2nd Grade (ages 7-8)
- **Skills Practiced**:
  - Addition (0-20, results ≤ 25)
  - Subtraction (0-20, non-negative results)
  - Multiplication (1-5 operands)

## 🚀 Quick Start

### Installation
```bash
npm install
npm run dev
```

Open browser to `http://localhost:5173`

### Browser Requirements
- Chrome 90+ (2021 or newer)
- Safari 14+ (2021 or newer)
- Firefox 88+ (2021 or newer)

## 🎮 How to Play

1. Read the math problem displayed on screen
2. Type your answer in the number box
3. Press Enter or click Submit
4. Get instant feedback from the friendly gorilla!
5. Keep practicing to improve your score

## 🏫 For Teachers & Parents

This game aligns with **Common Core Math Standards for 2nd Grade**:
- **CCSS.MATH.CONTENT.2.OA.B.2**: Fluently add and subtract within 20
- **CCSS.MATH.CONTENT.2.NBT.B.5**: Fluently add and subtract within 100
- **CCSS.MATH.CONTENT.3.OA.C.7**: Fluently multiply within 5 × 5 (early introduction)

### Classroom Use
- **No internet required** after initial load
- **Mute button** for quiet classrooms
- **Self-paced learning** (no time limits)
- **Positive reinforcement** (encouraging feedback)

## 🎨 Features

✅ **Color-coded operators** (green for +, red for -, blue for ×)
✅ **Animated gorilla mascot** that celebrates correct answers
✅ **Streak tracking** to motivate consistent performance
✅ **Accessibility-first design** with keyboard navigation
✅ **Large touch targets** (44px minimum - WCAG AAA compliant)
✅ **High contrast mode** support for visual accessibility
✅ **Responsive design** for tablets and desktops

## 🧪 Testing

```bash
npm run test        # Run unit and component tests
npm run test:ui     # Open Vitest UI
```

### Test Coverage
- ✅ Problem generation logic (100+ test cases)
- ✅ Component interaction flows
- ✅ Accessibility compliance (ARIA labels, keyboard navigation)

## 🚢 Deployment

### GitHub Pages

1. Update the `homepage` field in `package.json`:
   ```json
   "homepage": "https://YOUR_USERNAME.github.io/gorilla-math-game/"
   ```

2. Update the `base` in `vite.config.js`:
   ```javascript
   base: '/gorilla-math-game/'
   ```

3. Deploy:
   ```bash
   npm run deploy
   ```

The game will be available at: `https://YOUR_USERNAME.github.io/gorilla-math-game/`

## 📦 Technology Stack

- **Frontend**: Vite 5 + React 18
- **Styling**: CSS Modules (scoped, kid-friendly design)
- **State Management**: React Hooks (useState, useEffect)
- **Testing**: Vitest + React Testing Library
- **Deployment**: GitHub Pages

## 🎨 Customization

### Adding Sound Effects (Optional)

1. Place audio files in the `public/` directory:
   - `correct.mp3` - Success sound
   - `oops.mp3` - Retry sound

2. The game will automatically load and use them!

### Changing Problem Difficulty

Edit `src/utils/problemGenerator.js` to adjust:
- Number ranges for addition/subtraction
- Multiplication table size
- Problem type distribution

## 📁 Project Structure

```
gorilla-math-game/
├── index.html              # Vite entry point (ROOT location)
├── package.json            # Dependencies + scripts
├── vite.config.js          # Vite configuration
├── public/                 # Static assets
│   └── .gitkeep
├── src/
│   ├── main.jsx            # React entry point
│   ├── App.jsx             # Root component
│   ├── components/         # React components
│   │   ├── GameEngine.jsx
│   │   ├── ProblemDisplay.jsx
│   │   ├── AnswerInput.jsx
│   │   ├── FeedbackDisplay.jsx
│   │   ├── ScoreBoard.jsx
│   │   └── GorillaCharacter.jsx
│   ├── utils/              # Pure functions
│   │   ├── problemGenerator.js
│   │   └── soundPlayer.js
│   ├── styles/             # CSS Modules
│   │   ├── App.module.css
│   │   ├── GameEngine.module.css
│   │   ├── ProblemDisplay.module.css
│   │   ├── AnswerInput.module.css
│   │   ├── FeedbackDisplay.module.css
│   │   ├── ScoreBoard.module.css
│   │   └── GorillaCharacter.module.css
│   └── __tests__/          # Test files
│       ├── setup.js
│       ├── problemGenerator.test.js
│       ├── GameEngine.test.jsx
│       └── accessibility.test.jsx
└── dist/                   # Build output (git-ignored)
```

## 🐛 Troubleshooting

### Blank Page After Deployment
- Ensure `index.html` is in the **root** directory (not `public/`)
- Verify `base` in `vite.config.js` matches your repository name
- Check browser console for 404 errors on assets

### Tests Failing
- Run `npm install` to ensure all dependencies are installed
- Clear test cache: `npm run test -- --clearCache`

### Browser Compatibility Issues
- Check browser version meets minimum requirements
- Enable JavaScript in browser settings
- Try a different modern browser

## 🤝 Contributing

This is an educational project designed for 2nd graders. Contributions welcome!

### Ideas for Enhancement
- Add more problem types (division, fractions)
- Implement difficulty levels (easy, medium, hard)
- Add progress tracking with charts
- Create teacher dashboard for class monitoring
- Add more gorilla animations and reactions

## 📄 License

MIT License - Free for educational use

## 🎓 Credits

Created with ❤️ for young learners everywhere!

- **Framework**: Vite + React
- **Inspiration**: Making math fun and accessible for all students
- **Target Audience**: 2nd grade students (ages 7-8)

---

**Happy Learning! 🦍📚**
