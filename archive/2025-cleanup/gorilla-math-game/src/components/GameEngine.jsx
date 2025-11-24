import { useState, useEffect } from 'react'
import { generateRandomProblem } from '../utils/problemGenerator'
import { initSounds, playSound, toggleMute, isSoundMuted } from '../utils/soundPlayer'
import ProblemDisplay from './ProblemDisplay'
import AnswerInput from './AnswerInput'
import FeedbackDisplay from './FeedbackDisplay'
import ScoreBoard from './ScoreBoard'
import GorillaCharacter from './GorillaCharacter'
import styles from '../styles/GameEngine.module.css'

function GameEngine() {
  const [currentProblem, setCurrentProblem] = useState(() => generateRandomProblem())
  const [score, setScore] = useState(0)
  const [attempts, setAttempts] = useState(0)
  const [userAnswer, setUserAnswer] = useState('')
  const [feedbackState, setFeedbackState] = useState('idle')
  const [gorillaEmotion, setGorillaEmotion] = useState('thinking')
  const [muted, setMuted] = useState(false)
  const [streak, setStreak] = useState(0)

  // Initialize sounds on mount
  useEffect(() => {
    initSounds();
    setMuted(isSoundMuted());
  }, [])

  // Generate new problem
  const generateNewProblem = () => {
    setCurrentProblem(generateRandomProblem())
    setUserAnswer('')
    setFeedbackState('idle')
    setGorillaEmotion('thinking')
  }

  // Validate answer
  const validateAnswer = (answer) => {
    const numAnswer = parseInt(answer, 10)
    setAttempts(prev => prev + 1)

    if (numAnswer === currentProblem.correctAnswer) {
      handleCorrect()
    } else {
      handleIncorrect()
    }
  }

  // Handle correct answer
  const handleCorrect = () => {
    setScore(prev => prev + 1)
    setStreak(prev => prev + 1)
    setFeedbackState('correct')
    setGorillaEmotion('happy')
    playSound('correct')

    // Auto-advance to next problem after 2 seconds
    setTimeout(() => {
      generateNewProblem()
    }, 2000)
  }

  // Handle incorrect answer
  const handleIncorrect = () => {
    setStreak(0)
    setFeedbackState('incorrect')
    setGorillaEmotion('thinking')
    playSound('incorrect')

    // Reset feedback after 1.5 seconds to allow retry
    setTimeout(() => {
      setFeedbackState('idle')
      setUserAnswer('')
    }, 1500)
  }

  // Handle mute toggle
  const handleMuteToggle = () => {
    const newMutedState = toggleMute()
    setMuted(newMutedState)
  }

  return (
    <div className={styles.gameEngine}>
      <div className={styles.topBar}>
        <ScoreBoard score={score} attempts={attempts} streak={streak} />
        <button
          className={styles.muteButton}
          onClick={handleMuteToggle}
          aria-label={muted ? 'Unmute sounds' : 'Mute sounds'}
        >
          {muted ? '🔇' : '🔊'}
        </button>
      </div>

      <div className={styles.gameArea}>
        <GorillaCharacter emotion={gorillaEmotion} />
        <ProblemDisplay
          operand1={currentProblem.operand1}
          operand2={currentProblem.operand2}
          operator={currentProblem.operator}
        />
        <AnswerInput
          value={userAnswer}
          onChange={setUserAnswer}
          onSubmit={validateAnswer}
          disabled={feedbackState !== 'idle'}
        />
        <FeedbackDisplay feedbackState={feedbackState} />
      </div>
    </div>
  )
}

export default GameEngine
