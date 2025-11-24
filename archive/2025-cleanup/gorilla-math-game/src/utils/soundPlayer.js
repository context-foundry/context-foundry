/**
 * Sound Player Utility
 * Web Audio API wrapper for playing success/retry sound effects
 */

let audioContext;
const sounds = {};
let isMuted = false;

/**
 * Initialize sound system and load audio files
 */
export async function initSounds() {
  try {
    // Check if audio files exist before initializing
    audioContext = new (window.AudioContext || window.webkitAudioContext)();

    // Load mute preference from localStorage
    isMuted = localStorage.getItem('gorillaMathMuted') === 'true';

    // Try to load sounds (may fail if files don't exist yet)
    try {
      sounds.correct = await loadSound('/correct.mp3');
    } catch (e) {
      console.log('Correct sound not available (optional)');
    }

    try {
      sounds.incorrect = await loadSound('/oops.mp3');
    } catch (e) {
      console.log('Incorrect sound not available (optional)');
    }
  } catch (error) {
    console.log('Web Audio API not supported or sounds not available');
  }
}

/**
 * Load a sound file from URL
 * @param {string} url - Path to audio file
 * @returns {Promise<AudioBuffer>} Decoded audio buffer
 */
async function loadSound(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load sound: ${url}`);
  }
  const buffer = await response.arrayBuffer();
  return await audioContext.decodeAudioData(buffer);
}

/**
 * Play a named sound effect
 * @param {string} name - Sound name ('correct' or 'incorrect')
 */
export function playSound(name) {
  if (isMuted || !sounds[name] || !audioContext) return;

  try {
    const source = audioContext.createBufferSource();
    source.buffer = sounds[name];
    source.connect(audioContext.destination);
    source.start(0);
  } catch (error) {
    console.log('Error playing sound:', error);
  }
}

/**
 * Toggle mute state and persist to localStorage
 * @returns {boolean} New mute state
 */
export function toggleMute() {
  isMuted = !isMuted;
  localStorage.setItem('gorillaMathMuted', isMuted.toString());
  return isMuted;
}

/**
 * Get current mute state
 * @returns {boolean} Current mute state
 */
export function isSoundMuted() {
  return isMuted;
}
