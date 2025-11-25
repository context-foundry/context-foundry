# Interactive Tour - Website Integration Guide

## Quick Setup on VPS

```bash
# On VPS: /home/chuck/homelab/context-foundry/
git pull origin main
cp docs/interactive-tour.html public/interactive-tour.html
```

---

## Option 1: Hero Section with Iframe Embed (Recommended)

Replace the existing hero section in `public/index.html` with this:

```html
<!-- Hero Section with Interactive Visualization -->
<section id="hero" class="hero-section">
    <div class="hero-content">
        <h1 class="hero-title">
            <span class="gradient-text">Context Foundry</span>
        </h1>
        <p class="hero-subtitle">
            Autonomous AI Build System powered by Claude
        </p>
        <div class="hero-cta">
            <a href="#quick-start" class="btn btn-primary">Get Started</a>
            <a href="https://github.com/context-foundry/context-foundry" class="btn btn-secondary" target="_blank">
                View on GitHub
            </a>
        </div>
    </div>

    <!-- Interactive 3D Visualization -->
    <div class="hero-visualization">
        <iframe
            src="interactive-tour.html"
            title="Context Foundry Interactive Tour"
            frameborder="0"
            allowfullscreen
        ></iframe>
        <div class="viz-overlay">
            <span class="viz-hint">Click ☰ to start the tour</span>
        </div>
    </div>
</section>
```

Add this CSS to `public/css/styles.css` or inline in `<style>`:

```css
/* Hero Visualization Styles */
.hero-section {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    position: relative;
}

.hero-content {
    text-align: center;
    z-index: 10;
    margin-bottom: 2rem;
}

.hero-title {
    font-size: clamp(2.5rem, 8vw, 4.5rem);
    margin-bottom: 1rem;
}

.gradient-text {
    background: linear-gradient(135deg, #00d9ff, #00ff00);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.hero-subtitle {
    font-size: clamp(1rem, 3vw, 1.5rem);
    opacity: 0.8;
    margin-bottom: 2rem;
}

.hero-cta {
    display: flex;
    gap: 1rem;
    justify-content: center;
    flex-wrap: wrap;
}

.hero-visualization {
    width: 100%;
    max-width: 1200px;
    height: 600px;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(0, 217, 255, 0.3);
    box-shadow: 0 0 60px rgba(0, 217, 255, 0.15);
    position: relative;
}

.hero-visualization iframe {
    width: 100%;
    height: 100%;
    border: none;
}

.viz-overlay {
    position: absolute;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    pointer-events: none;
    z-index: 5;
}

.viz-hint {
    background: rgba(10, 10, 10, 0.9);
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 12px;
    color: #00d9ff;
    border: 1px solid rgba(0, 217, 255, 0.3);
    animation: pulse-hint 2s ease-in-out infinite;
}

@keyframes pulse-hint {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Responsive */
@media (max-width: 768px) {
    .hero-visualization {
        height: 400px;
    }
}

@media (max-width: 480px) {
    .hero-visualization {
        height: 300px;
    }

    .viz-hint {
        display: none;
    }
}
```

---

## Option 2: Full-Page Standalone (Link from Hero)

Keep existing hero but add a prominent link:

```html
<!-- Add to hero section -->
<div class="hero-cta">
    <a href="interactive-tour.html" class="btn btn-primary btn-large">
        🎮 Interactive Tour
    </a>
    <a href="#quick-start" class="btn btn-secondary">Get Started</a>
</div>
```

CSS for the large button:

```css
.btn-large {
    padding: 16px 32px;
    font-size: 1.2rem;
    animation: glow-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(0, 217, 255, 0.4); }
    50% { box-shadow: 0 0 40px rgba(0, 217, 255, 0.8); }
}
```

---

## Option 3: Background Visualization (Subtle)

Use the visualization as a subtle animated background:

```html
<section id="hero" class="hero-section">
    <div class="hero-bg-viz">
        <iframe src="interactive-tour.html" tabindex="-1"></iframe>
    </div>
    <div class="hero-content">
        <!-- Your existing hero content -->
    </div>
</section>
```

```css
.hero-section {
    position: relative;
    min-height: 100vh;
    overflow: hidden;
}

.hero-bg-viz {
    position: absolute;
    inset: 0;
    z-index: 1;
    opacity: 0.3;
    pointer-events: none;
}

.hero-bg-viz iframe {
    width: 100%;
    height: 100%;
    border: none;
    transform: scale(1.2);
}

.hero-content {
    position: relative;
    z-index: 10;
}
```

---

## Deployment Checklist

1. [ ] Pull latest from GitHub
2. [ ] Copy `docs/interactive-tour.html` to `public/`
3. [ ] Choose integration option and update `public/index.html`
4. [ ] Add CSS styles
5. [ ] Test locally: `cd public && python3 -m http.server 8000`
6. [ ] Commit and push:
   ```bash
   git add public/
   git commit -m "feat: Add interactive tour visualization to homepage"
   git push origin main
   ```
7. [ ] Verify at https://www.contextfoundry.dev (~2 min deploy)

---

## File Locations

| File | Location |
|------|----------|
| Visualization | `public/interactive-tour.html` |
| Main page | `public/index.html` |
| Styles | `public/css/styles.css` or `public/css/variables.css` |
| Direct URL | `https://www.contextfoundry.dev/interactive-tour.html` |
