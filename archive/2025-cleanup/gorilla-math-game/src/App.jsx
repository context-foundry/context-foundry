import { useEffect } from 'react'
import GameEngine from './components/GameEngine'
import styles from './styles/App.module.css'

function App() {
  // Browser compatibility check
  useEffect(() => {
    const isModernBrowser = 'replaceAll' in String.prototype;
    if (!isModernBrowser) {
      alert('This game requires a modern browser (Chrome 90+, Safari 14+, Firefox 88+)');
    }
  }, []);

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <h1 className={styles.title}>🦍 Gorilla Math Game</h1>
        <p className={styles.subtitle}>Practice your math skills with our friendly gorilla!</p>
      </header>
      <main className={styles.main}>
        <GameEngine />
      </main>
      <footer className={styles.footer}>
        <p>For 2nd Grade Students • Addition, Subtraction & Multiplication</p>
      </footer>
    </div>
  )
}

export default App
