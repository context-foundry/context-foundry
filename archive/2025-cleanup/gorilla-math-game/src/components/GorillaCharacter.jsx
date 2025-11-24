import { useEffect, useState } from 'react'
import styles from '../styles/GorillaCharacter.module.css'

function GorillaCharacter({ emotion }) {
  const [displayEmotion, setDisplayEmotion] = useState(emotion)
  const [isAnimating, setIsAnimating] = useState(false)

  useEffect(() => {
    if (emotion !== displayEmotion) {
      setIsAnimating(true)
      setDisplayEmotion(emotion)

      setTimeout(() => {
        setIsAnimating(false)
      }, 500)
    }
  }, [emotion, displayEmotion])

  const getGorillaEmoji = () => {
    switch (displayEmotion) {
      case 'happy':
        return '🎉 🦍 🎉'
      case 'thinking':
        return '🤔 🦍'
      default:
        return '🦍'
    }
  }

  const getMessage = () => {
    switch (displayEmotion) {
      case 'happy':
        return "Awesome! You got it right!"
      case 'thinking':
        return "You can do it!"
      default:
        return "Let's solve some problems!"
    }
  }

  return (
    <div className={\`\${styles.gorillaContainer} \${isAnimating ? styles.animating : ''}\`}>
      <div className={styles.character}>
        <div className={\`\${styles.gorilla} \${styles[displayEmotion]}\`}>
          {getGorillaEmoji()}
        </div>
        <div className={styles.speechBubble}>
          {getMessage()}
        </div>
      </div>
    </div>
  )
}

export default GorillaCharacter
