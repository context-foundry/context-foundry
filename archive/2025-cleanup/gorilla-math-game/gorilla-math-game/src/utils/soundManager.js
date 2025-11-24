// Optional Web Audio API sound manager
// Currently using placeholder implementation
// Can be extended with actual sound files in the future

class SoundManager {
  constructor() {
    this.audioContext = null;
    this.enabled = false;
  }

  /**
   * Initialize the audio context (requires user interaction)
   */
  init() {
    try {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
      this.enabled = true;
    } catch (error) {
      console.warn('Web Audio API not supported:', error);
      this.enabled = false;
    }
  }

  /**
   * Play success sound (placeholder)
   */
  playSuccess() {
    if (!this.enabled || !this.audioContext) return;

    // Simple beep sound using oscillator
    const oscillator = this.audioContext.createOscillator();
    const gainNode = this.audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(this.audioContext.destination);

    oscillator.frequency.value = 523.25; // C5 note
    gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.3);

    oscillator.start(this.audioContext.currentTime);
    oscillator.stop(this.audioContext.currentTime + 0.3);
  }

  /**
   * Play error sound (placeholder)
   */
  playError() {
    if (!this.enabled || !this.audioContext) return;

    // Lower pitch beep
    const oscillator = this.audioContext.createOscillator();
    const gainNode = this.audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(this.audioContext.destination);

    oscillator.frequency.value = 196.00; // G3 note
    gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.2);

    oscillator.start(this.audioContext.currentTime);
    oscillator.stop(this.audioContext.currentTime + 0.2);
  }
}

// Export singleton instance
export const soundManager = new SoundManager();
