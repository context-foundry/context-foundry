import styles from '../styles/ScoreBoard.module.css'

function ScoreBoard({ score, attempts, streak }) {
  const accuracy = attempts > 0 ? Math.round((score / attempts) * 100) : 0

  return (
    <div className={styles.scoreboard}>
      <div className={styles.scoreItem}>
        <span className={styles.label}>Score:</span>
        <span className={styles.value}>{score}</span>
      </div>
      <div className={styles.scoreItem}>
        <span className={styles.label}>Accuracy:</span>
        <span className={styles.value}>{accuracy}%</span>
      </div>
      {streak > 0 && (
        <div className={styles.scoreItem}>
          <span className={styles.label}>Streak:</span>
          <span className={styles.value}>🔥 {streak}</span>
        </div>
      )}
    </div>
  )
}

export default ScoreBoard
