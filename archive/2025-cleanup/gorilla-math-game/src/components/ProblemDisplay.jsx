import styles from '../styles/ProblemDisplay.module.css'

function ProblemDisplay({ operand1, operand2, operator }) {
  const getOperatorClass = () => {
    switch (operator) {
      case '+':
        return styles.operatorAdd
      case '-':
        return styles.operatorSubtract
      case '×':
        return styles.operatorMultiply
      default:
        return ''
    }
  }

  return (
    <div className={styles.problem} data-testid="problem-display">
      <span className={styles.number}>{operand1}</span>
      <span className={\`\${styles.operator} \${getOperatorClass()}\`}>
        {operator}
      </span>
      <span className={styles.number}>{operand2}</span>
      <span className={styles.equals}>=</span>
      <span className={styles.questionMark}>?</span>
    </div>
  )
}

export default ProblemDisplay
