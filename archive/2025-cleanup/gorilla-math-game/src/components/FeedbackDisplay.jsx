import styles from '../styles/FeedbackDisplay.module.css'

function FeedbackDisplay({ feedbackState }) {
  if (feedbackState === 'idle') {
    return null
  }

  const isCorrect = feedbackState === 'correct'

  return (
    <div
      className={\`\${styles.feedback} \${isCorrect ? styles.correct : styles.incorrect}\`}
      role="alert"
      aria-live="polite"
    >
      {isCorrect ? (
        <>
          <span className={styles.icon}>✓</span>
          <span className={styles.message}>Great job!</span>
        </>
      ) : (
        <>
          <span className={styles.icon}>✗</span>
          <span className={styles.message}>Try again!</span>
        </>
      )}
    </div>
  )
}

export default FeedbackDisplay
