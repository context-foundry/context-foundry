import { useEffect, useRef } from 'react'
import styles from '../styles/AnswerInput.module.css'

function AnswerInput({ value, onChange, onSubmit, disabled }) {
  const inputRef = useRef(null)

  // Auto-focus on mount and after re-enable
  useEffect(() => {
    if (!disabled && inputRef.current) {
      inputRef.current.focus()
    }
  }, [disabled])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (value.trim() !== '' && !disabled) {
      onSubmit(value)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSubmit(e)
    }
  }

  return (
    <div className={styles.answerInputContainer}>
      <label htmlFor="answer-input" className={styles.label}>
        Your Answer:
      </label>
      <div className={styles.inputGroup}>
        <input
          ref={inputRef}
          id="answer-input"
          type="number"
          className={styles.input}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={disabled}
          min="0"
          aria-label="Type your answer and press Enter"
          placeholder="?"
        />
        <button
          className={styles.submitButton}
          onClick={handleSubmit}
          disabled={disabled || value.trim() === ''}
          aria-label="Submit answer"
        >
          Submit
        </button>
      </div>
    </div>
  )
}

export default AnswerInput
