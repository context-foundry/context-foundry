# Context Foundry Marketing Website - Architecture Specification

**Project**: contextfoundry.dev marketing site
**Date**: 2025-10-25
**Architect Agent**: Context Foundry Architect v2.1.0
**Based on**: Scout Report v2.1.0

---

## Table of Contents

1. [Complete File Structure](#complete-file-structure)
2. [HTML Architecture](#html-architecture)
3. [CSS Architecture](#css-architecture)
4. [JavaScript Architecture](#javascript-architecture)
5. [Content Structure](#content-structure)
6. [Testing Requirements](#testing-requirements)
7. [Step-by-Step Implementation Plan](#step-by-step-implementation-plan)

---

## Complete File Structure

### Directory Tree

```
/home/chuck/homelab/context-foundry/public/
├── index.html                    # Main landing page (Priority: P0)
├── css/
│   ├── reset.css                 # CSS normalization (Priority: P0)
│   ├── variables.css             # Design tokens & custom properties (Priority: P0)
│   └── styles.css                # Main stylesheet (Priority: P0)
├── js/
│   ├── main.js                   # Primary functionality (Priority: P1)
│   └── navigation.js             # Mobile navigation logic (Priority: P1)
├── images/
│   ├── logo.svg                  # Context Foundry logo (Priority: P1)
│   ├── hero-gradient.svg         # Hero section background (Priority: P2)
│   └── og-image.png              # Social media preview (1200x630) (Priority: P2)
├── favicon.ico                   # Browser favicon (Priority: P2)
└── robots.txt                    # SEO crawler instructions (Priority: P2)
```

### File Purposes

| File | Size Estimate | Purpose | Dependencies |
|------|---------------|---------|--------------|
| `index.html` | ~15KB | Semantic structure, content, SEO meta | None |
| `css/reset.css` | ~2KB | Browser consistency baseline | None |
| `css/variables.css` | ~3KB | Design tokens (colors, spacing, typography) | None |
| `css/styles.css` | ~25KB | Layout, components, responsive styles | reset.css, variables.css |
| `js/main.js` | ~3KB | Smooth scroll, analytics hooks | None |
| `js/navigation.js` | ~5KB | Mobile menu toggle, accessibility | None |
| `images/logo.svg` | ~2KB | Scalable brand mark | None |
| `images/hero-gradient.svg` | ~5KB | Decorative background | None |
| `images/og-image.png` | ~150KB | Social preview image | None |

**Total estimated size**: ~210KB (uncompressed), ~80KB (gzipped)

---

## HTML Architecture

### Document Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Meta & SEO -->
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Context Foundry - Autonomous AI Development | Build Complete Software While You Sleep</title>
  <meta name="description" content="AI that autonomously codes, tests, and deploys. From idea to GitHub in 7-15 minutes. Self-healing tests, parallel execution, fresh contexts.">

  <!-- Open Graph / Facebook -->
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://contextfoundry.dev/">
  <meta property="og:title" content="Context Foundry - Autonomous AI Development">
  <meta property="og:description" content="Build complete software while you sleep. AI that codes, tests, and deploys autonomously.">
  <meta property="og:image" content="https://contextfoundry.dev/images/og-image.png">

  <!-- Twitter -->
  <meta property="twitter:card" content="summary_large_image">
  <meta property="twitter:url" content="https://contextfoundry.dev/">
  <meta property="twitter:title" content="Context Foundry - Autonomous AI Development">
  <meta property="twitter:description" content="Build complete software while you sleep. AI that codes, tests, and deploys autonomously.">
  <meta property="twitter:image" content="https://contextfoundry.dev/images/og-image.png">

  <!-- Favicon -->
  <link rel="icon" type="image/x-icon" href="/favicon.ico">

  <!-- Stylesheets -->
  <link rel="stylesheet" href="/css/reset.css">
  <link rel="stylesheet" href="/css/variables.css">
  <link rel="stylesheet" href="/css/styles.css">

  <!-- Preload critical assets -->
  <link rel="preload" href="/css/variables.css" as="style">
</head>
<body>
  <!-- Site structure follows -->
</body>
</html>
```

### Semantic HTML Structure

```html
<body>
  <!-- HEADER / NAVIGATION -->
  <header class="site-header" role="banner">
    <nav class="main-nav" role="navigation" aria-label="Main navigation">
      <!-- Logo + Desktop Nav + Mobile Toggle -->
    </nav>
  </header>

  <!-- MAIN CONTENT -->
  <main class="site-main" role="main">

    <!-- SECTION 1: Hero -->
    <section id="hero" class="hero-section">
      <!-- Headline, subheadline, CTAs -->
    </section>

    <!-- SECTION 2: Features -->
    <section id="features" class="features-section">
      <!-- Feature grid with icons -->
    </section>

    <!-- SECTION 3: How It Works -->
    <section id="how-it-works" class="pipeline-section">
      <!-- Visual pipeline diagram -->
    </section>

    <!-- SECTION 4: Quick Start -->
    <section id="quick-start" class="quickstart-section">
      <!-- Code examples, installation steps -->
    </section>

    <!-- SECTION 5: Metrics / Social Proof -->
    <section id="metrics" class="metrics-section">
      <!-- Build time stats, GitHub stars -->
    </section>

    <!-- SECTION 6: CTA / Footer -->
    <section id="cta" class="cta-section">
      <!-- Final call-to-action -->
    </section>

  </main>

  <!-- FOOTER -->
  <footer class="site-footer" role="contentinfo">
    <!-- Links, copyright, social -->
  </footer>

  <!-- SCRIPTS -->
  <script src="/js/navigation.js" defer></script>
  <script src="/js/main.js" defer></script>
</body>
```

### Component Breakdown

#### 1. Header/Navigation Component

**Desktop View (>768px)**:
```html
<header class="site-header">
  <nav class="main-nav">
    <a href="/" class="logo" aria-label="Context Foundry home">
      <img src="/images/logo.svg" alt="Context Foundry" width="40" height="40">
      <span class="logo-text">Context Foundry</span>
    </a>

    <ul class="nav-links" role="list">
      <li><a href="#features">Features</a></li>
      <li><a href="#how-it-works">How It Works</a></li>
      <li><a href="#quick-start">Quick Start</a></li>
      <li><a href="https://github.com/context-foundry/context-foundry" class="nav-link-github" target="_blank" rel="noopener">
        GitHub
      </a></li>
    </ul>

    <!-- Mobile toggle button -->
    <button class="mobile-menu-toggle" aria-label="Toggle mobile menu" aria-expanded="false">
      <span class="hamburger-icon"></span>
    </button>
  </nav>
</header>
```

**Mobile View (<768px)**:
- Hamburger icon (3 lines)
- Slide-in drawer from right
- Overlay backdrop
- Close button

#### 2. Hero Section Component

```html
<section id="hero" class="hero-section">
  <div class="hero-content">
    <h1 class="hero-headline">
      Build Complete Software <span class="gradient-text">While You Sleep</span>
    </h1>

    <p class="hero-subheadline">
      AI that autonomously codes, tests, and deploys—from idea to GitHub in 7-15 minutes
    </p>

    <div class="hero-cta-group">
      <a href="#quick-start" class="btn btn-primary">
        Get Started
        <svg class="btn-icon" aria-hidden="true"><!-- Arrow icon --></svg>
      </a>
      <a href="https://github.com/context-foundry/context-foundry" class="btn btn-secondary" target="_blank" rel="noopener">
        View on GitHub
        <svg class="btn-icon" aria-hidden="true"><!-- GitHub icon --></svg>
      </a>
    </div>

    <!-- Visual indicator: scroll down -->
    <a href="#features" class="scroll-indicator" aria-label="Scroll to features">
      <svg><!-- Down arrow --></svg>
    </a>
  </div>

  <!-- Background decoration -->
  <div class="hero-background" aria-hidden="true">
    <img src="/images/hero-gradient.svg" alt="" loading="lazy">
  </div>
</section>
```

#### 3. Features Section Component

```html
<section id="features" class="features-section">
  <div class="section-container">
    <header class="section-header">
      <h2 class="section-title">Why Context Foundry?</h2>
      <p class="section-subtitle">
        The only AI that truly works autonomously. Walk away and come back to production-ready software.
      </p>
    </header>

    <div class="features-grid">

      <!-- Feature Card 1 -->
      <article class="feature-card">
        <div class="feature-icon" aria-hidden="true">
          <svg><!-- Autonomous icon --></svg>
        </div>
        <h3 class="feature-title">Autonomous Build</h3>
        <p class="feature-description">
          Describe what you want, then walk away. Come back to complete, tested, deployed applications.
        </p>
      </article>

      <!-- Feature Card 2 -->
      <article class="feature-card">
        <div class="feature-icon" aria-hidden="true">
          <svg><!-- Self-healing icon --></svg>
        </div>
        <h3 class="feature-title">Self-Healing Tests</h3>
        <p class="feature-description">
          Tests fail? Context Foundry automatically fixes them. Up to 3 retry attempts with intelligent debugging.
        </p>
      </article>

      <!-- Feature Card 3 -->
      <article class="feature-card">
        <div class="feature-icon" aria-hidden="true">
          <svg><!-- Parallel icon --></svg>
        </div>
        <h3 class="feature-title">Parallel Execution</h3>
        <p class="feature-description">
          2-8 concurrent builders working simultaneously. 3x faster than sequential builds.
        </p>
      </article>

      <!-- Feature Card 4 -->
      <article class="feature-card">
        <div class="feature-icon" aria-hidden="true">
          <svg><!-- Context icon --></svg>
        </div>
        <h3 class="feature-title">Fresh Contexts</h3>
        <p class="feature-description">
          Each spawned agent gets a clean 200K token window. No context pollution, no token accumulation.
        </p>
      </article>

      <!-- Feature Card 5 -->
      <article class="feature-card">
        <div class="feature-icon" aria-hidden="true">
          <svg><!-- Learning icon --></svg>
        </div>
        <h3 class="feature-title">Pattern Learning</h3>
        <p class="feature-description">
          Captures successful patterns automatically. Gets smarter with every build you run.
        </p>
      </article>

      <!-- Feature Card 6 -->
      <article class="feature-card">
        <div class="feature-icon" aria-hidden="true">
          <svg><!-- Deploy icon --></svg>
        </div>
        <h3 class="feature-title">Auto-Deploy</h3>
        <p class="feature-description">
          Automatically creates GitHub repos, commits code, pushes changes. Zero manual deployment.
        </p>
      </article>

    </div>
  </div>
</section>
```

#### 4. How It Works Section Component

```html
<section id="how-it-works" class="pipeline-section">
  <div class="section-container">
    <header class="section-header">
      <h2 class="section-title">The Autonomous Pipeline</h2>
      <p class="section-subtitle">
        Five specialized agents working in sequence, each with fresh context
      </p>
    </header>

    <div class="pipeline-flow">

      <!-- Stage 1 -->
      <article class="pipeline-stage">
        <div class="stage-number" aria-hidden="true">1</div>
        <div class="stage-icon" aria-hidden="true">
          <svg><!-- Scout icon --></svg>
        </div>
        <h3 class="stage-title">Scout</h3>
        <p class="stage-description">
          Researches requirements, analyzes technical constraints, recommends architecture
        </p>
        <div class="stage-output">
          Output: <code>scout-report.md</code>
        </div>
      </article>

      <!-- Connector arrow -->
      <div class="pipeline-connector" aria-hidden="true">
        <svg><!-- Right arrow --></svg>
      </div>

      <!-- Stage 2 -->
      <article class="pipeline-stage">
        <div class="stage-number" aria-hidden="true">2</div>
        <div class="stage-icon" aria-hidden="true">
          <svg><!-- Architect icon --></svg>
        </div>
        <h3 class="stage-title">Architect</h3>
        <p class="stage-description">
          Designs system architecture, file structure, component specifications
        </p>
        <div class="stage-output">
          Output: <code>architecture.md</code>
        </div>
      </article>

      <!-- Connector arrow -->
      <div class="pipeline-connector" aria-hidden="true">
        <svg><!-- Right arrow --></svg>
      </div>

      <!-- Stage 3 -->
      <article class="pipeline-stage">
        <div class="stage-number" aria-hidden="true">3</div>
        <div class="stage-icon" aria-hidden="true">
          <svg><!-- Builder icon --></svg>
        </div>
        <h3 class="stage-title">Builder</h3>
        <p class="stage-description">
          Implements code, writes tests, creates documentation (parallel execution)
        </p>
        <div class="stage-output">
          Output: <code>Working software + tests</code>
        </div>
      </article>

      <!-- Connector arrow -->
      <div class="pipeline-connector" aria-hidden="true">
        <svg><!-- Right arrow --></svg>
      </div>

      <!-- Stage 4 -->
      <article class="pipeline-stage">
        <div class="stage-number" aria-hidden="true">4</div>
        <div class="stage-icon" aria-hidden="true">
          <svg><!-- Tester icon --></svg>
        </div>
        <h3 class="stage-title">Tester</h3>
        <p class="stage-description">
          Validates functionality, auto-fixes failures, captures screenshots
        </p>
        <div class="stage-output">
          Output: <code>All tests passing ✓</code>
        </div>
      </article>

      <!-- Connector arrow -->
      <div class="pipeline-connector" aria-hidden="true">
        <svg><!-- Right arrow --></svg>
      </div>

      <!-- Stage 5 -->
      <article class="pipeline-stage">
        <div class="stage-number" aria-hidden="true">5</div>
        <div class="stage-icon" aria-hidden="true">
          <svg><!-- Deploy icon --></svg>
        </div>
        <h3 class="stage-title">Deploy</h3>
        <p class="stage-description">
          Creates repo, commits changes, pushes to GitHub, generates docs
        </p>
        <div class="stage-output">
          Output: <code>github.com/user/project</code>
        </div>
      </article>

    </div>

    <!-- Meta-MCP callout -->
    <div class="pipeline-innovation">
      <h4>The Breakthrough: Meta-MCP</h4>
      <p>
        Context Foundry doesn't just call external tools—it <strong>recursively spawns fresh Claude instances</strong>.
        Each agent gets its own clean 200K context window, enabling true autonomous operation.
      </p>
      <a href="https://github.com/context-foundry/context-foundry/blob/main/docs/INNOVATIONS.md" class="text-link" target="_blank" rel="noopener">
        Read the technical breakdown →
      </a>
    </div>

  </div>
</section>
```

#### 5. Quick Start Section Component

```html
<section id="quick-start" class="quickstart-section">
  <div class="section-container">
    <header class="section-header">
      <h2 class="section-title">Get Started in 3 Steps</h2>
      <p class="section-subtitle">
        Ready to build autonomously? Install takes less than 5 minutes.
      </p>
    </header>

    <div class="quickstart-steps">

      <!-- Step 1 -->
      <article class="quickstart-step">
        <div class="step-number">1</div>
        <h3 class="step-title">Install MCP Server</h3>
        <div class="code-block">
          <pre><code class="language-bash"><span class="comment"># Clone the repository</span>
git clone https://github.com/context-foundry/context-foundry.git
cd context-foundry

<span class="comment"># Install dependencies</span>
pip install -r requirements-mcp.txt</code></pre>
          <button class="copy-button" aria-label="Copy code">
            <svg><!-- Copy icon --></svg>
          </button>
        </div>
      </article>

      <!-- Step 2 -->
      <article class="quickstart-step">
        <div class="step-number">2</div>
        <h3 class="step-title">Configure Claude Code</h3>
        <div class="code-block">
          <pre><code class="language-bash"><span class="comment"># Add MCP server to Claude Code</span>
claude mcp add context-foundry \\
  --command python \\
  --args /path/to/context-foundry/mcp_server.py</code></pre>
          <button class="copy-button" aria-label="Copy code">
            <svg><!-- Copy icon --></svg>
          </button>
        </div>
      </article>

      <!-- Step 3 -->
      <article class="quickstart-step">
        <div class="step-number">3</div>
        <h3 class="step-title">Build Something Amazing</h3>
        <div class="code-block">
          <pre><code class="language-bash"><span class="comment"># Just ask naturally in Claude Code</span>
<span class="string">"Build a todo app with React and TypeScript"</span>

<span class="comment"># Walk away. Come back to deployed code.</span></code></pre>
          <button class="copy-button" aria-label="Copy code">
            <svg><!-- Copy icon --></svg>
          </button>
        </div>
      </article>

    </div>

    <!-- Additional resources -->
    <div class="quickstart-footer">
      <p class="quickstart-note">
        Need detailed setup instructions? Check the
        <a href="https://github.com/context-foundry/context-foundry/blob/main/QUICKSTART.md" target="_blank" rel="noopener">Quick Start Guide</a>
        or
        <a href="https://github.com/context-foundry/context-foundry/blob/main/USER_GUIDE.md" target="_blank" rel="noopener">User Guide</a>
      </p>
    </div>

  </div>
</section>
```

#### 6. Metrics Section Component

```html
<section id="metrics" class="metrics-section">
  <div class="section-container">
    <div class="metrics-grid">

      <div class="metric-card">
        <div class="metric-value">7-15 min</div>
        <div class="metric-label">Average Build Time</div>
      </div>

      <div class="metric-card">
        <div class="metric-value">200K</div>
        <div class="metric-label">Fresh Token Windows</div>
      </div>

      <div class="metric-card">
        <div class="metric-value">3x</div>
        <div class="metric-label">Faster with Parallel</div>
      </div>

      <div class="metric-card">
        <div class="metric-value">100%</div>
        <div class="metric-label">Autonomous</div>
      </div>

    </div>
  </div>
</section>
```

#### 7. CTA Section Component

```html
<section id="cta" class="cta-section">
  <div class="section-container">
    <h2 class="cta-headline">Ready to Build Autonomously?</h2>
    <p class="cta-subheadline">
      Join developers who ship complete projects while they sleep
    </p>
    <div class="cta-buttons">
      <a href="#quick-start" class="btn btn-primary btn-large">
        Get Started Now
      </a>
      <a href="https://github.com/context-foundry/context-foundry" class="btn btn-secondary btn-large" target="_blank" rel="noopener">
        Star on GitHub
      </a>
    </div>
  </div>
</section>
```

#### 8. Footer Component

```html
<footer class="site-footer">
  <div class="footer-container">

    <div class="footer-grid">

      <!-- Column 1: Brand -->
      <div class="footer-column">
        <div class="footer-logo">
          <img src="/images/logo.svg" alt="Context Foundry" width="32" height="32">
          <span>Context Foundry</span>
        </div>
        <p class="footer-tagline">
          Build complete software autonomously
        </p>
      </div>

      <!-- Column 2: Documentation -->
      <div class="footer-column">
        <h4 class="footer-heading">Documentation</h4>
        <ul class="footer-links" role="list">
          <li><a href="https://github.com/context-foundry/context-foundry/blob/main/QUICKSTART.md" target="_blank" rel="noopener">Quick Start</a></li>
          <li><a href="https://github.com/context-foundry/context-foundry/blob/main/USER_GUIDE.md" target="_blank" rel="noopener">User Guide</a></li>
          <li><a href="https://github.com/context-foundry/context-foundry/blob/main/docs/INNOVATIONS.md" target="_blank" rel="noopener">Technical Innovations</a></li>
          <li><a href="https://github.com/context-foundry/context-foundry/blob/main/CHANGELOG.md" target="_blank" rel="noopener">Changelog</a></li>
        </ul>
      </div>

      <!-- Column 3: Resources -->
      <div class="footer-column">
        <h4 class="footer-heading">Resources</h4>
        <ul class="footer-links" role="list">
          <li><a href="https://github.com/context-foundry/context-foundry" target="_blank" rel="noopener">GitHub Repository</a></li>
          <li><a href="https://github.com/context-foundry/context-foundry/issues" target="_blank" rel="noopener">Report Issues</a></li>
          <li><a href="https://github.com/context-foundry/context-foundry/discussions" target="_blank" rel="noopener">Discussions</a></li>
          <li><a href="https://github.com/context-foundry/context-foundry/blob/main/LICENSE" target="_blank" rel="noopener">MIT License</a></li>
        </ul>
      </div>

      <!-- Column 4: Connect -->
      <div class="footer-column">
        <h4 class="footer-heading">Connect</h4>
        <ul class="footer-links" role="list">
          <li><a href="https://twitter.com/contextfoundry" target="_blank" rel="noopener">Twitter/X</a></li>
          <li><a href="https://linkedin.com/company/context-foundry" target="_blank" rel="noopener">LinkedIn</a></li>
          <li><a href="mailto:hello@contextfoundry.dev">Contact</a></li>
        </ul>
      </div>

    </div>

    <!-- Copyright bar -->
    <div class="footer-bottom">
      <p class="copyright">
        © 2025 Context Foundry. Open source under MIT License.
      </p>
      <p class="version">
        Version 2.1.0
      </p>
    </div>

  </div>
</footer>
```

### SEO Meta Tags (Complete List)

```html
<!-- Essential Meta -->
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">

<!-- Primary Meta Tags -->
<title>Context Foundry - Autonomous AI Development | Build Complete Software While You Sleep</title>
<meta name="title" content="Context Foundry - Autonomous AI Development">
<meta name="description" content="AI that autonomously codes, tests, and deploys. From idea to GitHub in 7-15 minutes. Self-healing tests, parallel execution, fresh contexts.">
<meta name="keywords" content="AI development, autonomous coding, Claude AI, MCP server, automated testing, GitHub deployment, AI agents">
<meta name="author" content="Context Foundry Team">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://contextfoundry.dev/">

<!-- Open Graph / Facebook -->
<meta property="og:type" content="website">
<meta property="og:url" content="https://contextfoundry.dev/">
<meta property="og:site_name" content="Context Foundry">
<meta property="og:title" content="Context Foundry - Autonomous AI Development">
<meta property="og:description" content="Build complete software while you sleep. AI that codes, tests, and deploys autonomously.">
<meta property="og:image" content="https://contextfoundry.dev/images/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Context Foundry - Autonomous AI Development Platform">
<meta property="og:locale" content="en_US">

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@contextfoundry">
<meta name="twitter:creator" content="@contextfoundry">
<meta name="twitter:url" content="https://contextfoundry.dev/">
<meta name="twitter:title" content="Context Foundry - Autonomous AI Development">
<meta name="twitter:description" content="Build complete software while you sleep. AI that codes, tests, and deploys autonomously.">
<meta name="twitter:image" content="https://contextfoundry.dev/images/og-image.png">
<meta name="twitter:image:alt" content="Context Foundry - Autonomous AI Development Platform">

<!-- Additional SEO -->
<meta name="theme-color" content="#00d9ff">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="format-detection" content="telephone=no">

<!-- Structured Data (JSON-LD) -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Context Foundry",
  "description": "Autonomous AI development platform that builds complete software",
  "applicationCategory": "DeveloperApplication",
  "operatingSystem": "Cross-platform",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "5",
    "ratingCount": "1"
  }
}
</script>
```

---

## CSS Architecture

### Design System

#### Color Palette (variables.css)

```css
:root {
  /* Brand Colors */
  --color-primary: #00d9ff;           /* Electric cyan */
  --color-primary-hover: #00b8d9;     /* Darker cyan */
  --color-primary-dark: #0096b3;      /* Even darker */

  --color-secondary: #00ff00;         /* Bright green */
  --color-secondary-hover: #00cc00;   /* Darker green */

  --color-accent: #ff00ff;            /* Magenta */
  --color-accent-2: #a855f7;          /* Purple */

  /* Background Colors */
  --color-bg-primary: #0a0a0a;        /* Deepest black */
  --color-bg-secondary: #111827;      /* Slightly lighter */
  --color-bg-tertiary: #1f2937;       /* Card backgrounds */
  --color-bg-code: #0d1117;           /* Code blocks */

  /* Text Colors */
  --color-text-primary: #ffffff;      /* Pure white */
  --color-text-secondary: #e0e0e0;    /* Light gray */
  --color-text-tertiary: #9ca3af;     /* Medium gray */
  --color-text-muted: #6b7280;        /* Muted gray */

  /* Border Colors */
  --color-border: #374151;            /* Subtle borders */
  --color-border-hover: #4b5563;      /* Hover state */

  /* Status Colors */
  --color-success: #10b981;           /* Green */
  --color-warning: #f59e0b;           /* Amber */
  --color-error: #ef4444;             /* Red */
  --color-info: #3b82f6;              /* Blue */

  /* Gradient Overlays */
  --gradient-hero: linear-gradient(135deg,
    rgba(0, 217, 255, 0.1) 0%,
    rgba(168, 85, 247, 0.1) 100%);
  --gradient-accent: linear-gradient(90deg,
    var(--color-primary) 0%,
    var(--color-accent-2) 100%);
}
```

#### Typography System (variables.css)

```css
:root {
  /* Font Families */
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
               'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'Monaco', 'Menlo', 'Courier New', monospace;

  /* Font Sizes - Fluid Typography */
  --font-size-xs: clamp(0.75rem, 0.7rem + 0.2vw, 0.875rem);    /* 12-14px */
  --font-size-sm: clamp(0.875rem, 0.8rem + 0.3vw, 1rem);       /* 14-16px */
  --font-size-base: clamp(1rem, 0.95rem + 0.4vw, 1.125rem);    /* 16-18px */
  --font-size-md: clamp(1.125rem, 1rem + 0.5vw, 1.25rem);      /* 18-20px */
  --font-size-lg: clamp(1.25rem, 1.1rem + 0.6vw, 1.5rem);      /* 20-24px */
  --font-size-xl: clamp(1.5rem, 1.3rem + 0.8vw, 2rem);         /* 24-32px */
  --font-size-2xl: clamp(2rem, 1.7rem + 1.2vw, 3rem);          /* 32-48px */
  --font-size-3xl: clamp(2.5rem, 2rem + 2vw, 4rem);            /* 40-64px */

  /* Font Weights */
  --font-weight-normal: 400;
  --font-weight-medium: 500;
  --font-weight-semibold: 600;
  --font-weight-bold: 700;

  /* Line Heights */
  --line-height-tight: 1.25;
  --line-height-normal: 1.5;
  --line-height-relaxed: 1.75;

  /* Letter Spacing */
  --letter-spacing-tight: -0.025em;
  --letter-spacing-normal: 0;
  --letter-spacing-wide: 0.025em;
}
```

#### Spacing System (variables.css)

```css
:root {
  /* Base unit: 8px */
  --space-1: 0.5rem;    /* 8px */
  --space-2: 1rem;      /* 16px */
  --space-3: 1.5rem;    /* 24px */
  --space-4: 2rem;      /* 32px */
  --space-5: 2.5rem;    /* 40px */
  --space-6: 3rem;      /* 48px */
  --space-8: 4rem;      /* 64px */
  --space-10: 5rem;     /* 80px */
  --space-12: 6rem;     /* 96px */
  --space-16: 8rem;     /* 128px */
  --space-20: 10rem;    /* 160px */

  /* Section Spacing */
  --section-padding-mobile: var(--space-8);   /* 64px */
  --section-padding-tablet: var(--space-12);  /* 96px */
  --section-padding-desktop: var(--space-16); /* 128px */

  /* Container Max Width */
  --container-max-width: 1280px;
  --container-padding: var(--space-4);
}
```

#### Border Radius System (variables.css)

```css
:root {
  --radius-sm: 0.25rem;   /* 4px */
  --radius-md: 0.5rem;    /* 8px */
  --radius-lg: 0.75rem;   /* 12px */
  --radius-xl: 1rem;      /* 16px */
  --radius-2xl: 1.5rem;   /* 24px */
  --radius-full: 9999px;  /* Circular */
}
```

#### Shadow System (variables.css)

```css
:root {
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 10px 15px rgba(0, 0, 0, 0.5);
  --shadow-xl: 0 20px 25px rgba(0, 0, 0, 0.6);
  --shadow-glow: 0 0 20px rgba(0, 217, 255, 0.3);
  --shadow-glow-hover: 0 0 30px rgba(0, 217, 255, 0.5);
}
```

#### Transitions (variables.css)

```css
:root {
  --transition-fast: 150ms ease;
  --transition-base: 250ms ease;
  --transition-slow: 350ms ease;
  --transition-bounce: 400ms cubic-bezier(0.68, -0.55, 0.265, 1.55);
}
```

#### Breakpoints (variables.css)

```css
:root {
  --breakpoint-mobile: 320px;
  --breakpoint-tablet: 768px;
  --breakpoint-desktop: 1024px;
  --breakpoint-wide: 1440px;
}

/* Media query mixins (as comments for reference) */
/*
  Mobile-first approach:
  - Base styles: < 768px
  - Tablet: 768px - 1023px
  - Desktop: 1024px - 1439px
  - Wide: ≥ 1440px
*/
```

### Layout Strategy

#### Container System (styles.css)

```css
.section-container {
  width: 100%;
  max-width: var(--container-max-width);
  margin-left: auto;
  margin-right: auto;
  padding-left: var(--container-padding);
  padding-right: var(--container-padding);
}

/* Full-width sections */
.section-full {
  width: 100%;
  padding-left: 0;
  padding-right: 0;
}

/* Narrow content (for reading) */
.content-narrow {
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
}
```

#### Grid System (styles.css)

```css
/* Features Grid - Mobile first */
.features-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

@media (min-width: 768px) {
  .features-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: var(--space-6);
  }
}

@media (min-width: 1024px) {
  .features-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* Pipeline Flow - Horizontal on desktop */
.pipeline-flow {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

@media (min-width: 1024px) {
  .pipeline-flow {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }
}
```

### Component Styles

#### Buttons (styles.css)

```css
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-4);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
  font-family: var(--font-sans);
  text-decoration: none;
  border: 2px solid transparent;
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--transition-base);
  white-space: nowrap;
}

.btn-primary {
  background: var(--color-primary);
  color: var(--color-bg-primary);
  border-color: var(--color-primary);
}

.btn-primary:hover,
.btn-primary:focus {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
  box-shadow: var(--shadow-glow-hover);
  transform: translateY(-2px);
}

.btn-secondary {
  background: transparent;
  color: var(--color-text-primary);
  border-color: var(--color-border);
}

.btn-secondary:hover,
.btn-secondary:focus {
  background: var(--color-bg-tertiary);
  border-color: var(--color-border-hover);
}

.btn-large {
  padding: var(--space-3) var(--space-6);
  font-size: var(--font-size-lg);
}

.btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
```

#### Cards (styles.css)

```css
.feature-card {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  padding: var(--space-6);
  transition: all var(--transition-base);
}

.feature-card:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-lg);
  transform: translateY(-4px);
}

.feature-icon {
  width: 48px;
  height: 48px;
  margin-bottom: var(--space-3);
  color: var(--color-primary);
}

.feature-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.feature-description {
  font-size: var(--font-size-base);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}
```

#### Code Blocks (styles.css)

```css
.code-block {
  position: relative;
  background: var(--color-bg-code);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin: var(--space-4) 0;
}

.code-block pre {
  margin: 0;
  padding: var(--space-4);
  overflow-x: auto;
  font-family: var(--font-mono);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-relaxed);
  color: var(--color-text-secondary);
}

.code-block code {
  font-family: inherit;
}

/* Syntax highlighting */
.comment {
  color: var(--color-text-muted);
  font-style: italic;
}

.string {
  color: var(--color-secondary);
}

.keyword {
  color: var(--color-primary);
  font-weight: var(--font-weight-medium);
}

.function {
  color: var(--color-accent-2);
}

/* Copy button */
.copy-button {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  padding: var(--space-1) var(--space-2);
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  opacity: 0;
}

.code-block:hover .copy-button {
  opacity: 1;
}

.copy-button:hover {
  background: var(--color-bg-secondary);
  color: var(--color-text-primary);
}
```

### Responsive Design Strategy

**Mobile First Approach:**

```css
/* Base styles (mobile) */
.hero-headline {
  font-size: var(--font-size-2xl);  /* 32-48px */
}

/* Tablet (768px+) */
@media (min-width: 768px) {
  .hero-headline {
    font-size: var(--font-size-3xl);  /* 40-64px */
  }
}

/* Desktop (1024px+) */
@media (min-width: 1024px) {
  .hero-headline {
    font-size: 4.5rem;  /* 72px */
  }
}
```

### Animation Patterns

```css
/* Fade in on scroll */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-on-scroll {
  animation: fadeInUp 0.6s ease forwards;
}

/* Gradient text animation */
@keyframes gradientShift {
  0% {
    background-position: 0% 50%;
  }
  50% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}

.gradient-text {
  background: var(--gradient-accent);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  animation: gradientShift 3s ease infinite;
}

/* Pulse glow effect */
@keyframes pulseGlow {
  0%, 100% {
    box-shadow: var(--shadow-glow);
  }
  50% {
    box-shadow: var(--shadow-glow-hover);
  }
}

.glow-effect {
  animation: pulseGlow 2s ease infinite;
}
```

---

## JavaScript Architecture

### Mobile Navigation Logic (navigation.js)

```javascript
/**
 * Mobile Navigation Handler
 * Handles hamburger menu toggle, accessibility, and body scroll lock
 */

(function() {
  'use strict';

  // DOM elements
  const mobileToggle = document.querySelector('.mobile-menu-toggle');
  const nav = document.querySelector('.main-nav');
  const navLinks = document.querySelectorAll('.nav-links a');
  const body = document.body;

  // State
  let isMenuOpen = false;

  /**
   * Toggle mobile menu
   */
  function toggleMenu() {
    isMenuOpen = !isMenuOpen;

    // Update ARIA attributes
    mobileToggle.setAttribute('aria-expanded', isMenuOpen);

    // Toggle classes
    nav.classList.toggle('menu-open', isMenuOpen);
    mobileToggle.classList.toggle('active', isMenuOpen);

    // Prevent body scroll when menu is open
    if (isMenuOpen) {
      body.style.overflow = 'hidden';
    } else {
      body.style.overflow = '';
    }
  }

  /**
   * Close menu
   */
  function closeMenu() {
    if (isMenuOpen) {
      toggleMenu();
    }
  }

  /**
   * Handle click outside menu
   */
  function handleOutsideClick(e) {
    if (isMenuOpen && !nav.contains(e.target)) {
      closeMenu();
    }
  }

  /**
   * Handle escape key
   */
  function handleEscapeKey(e) {
    if (e.key === 'Escape' && isMenuOpen) {
      closeMenu();
    }
  }

  // Event listeners
  if (mobileToggle) {
    mobileToggle.addEventListener('click', toggleMenu);
  }

  // Close menu when clicking nav links
  navLinks.forEach(link => {
    link.addEventListener('click', closeMenu);
  });

  // Close menu on outside click
  document.addEventListener('click', handleOutsideClick);

  // Close menu on escape key
  document.addEventListener('keydown', handleEscapeKey);

  // Close menu on window resize (above mobile breakpoint)
  window.addEventListener('resize', function() {
    if (window.innerWidth >= 768 && isMenuOpen) {
      closeMenu();
    }
  });

})();
```

### Main JavaScript (main.js)

```javascript
/**
 * Context Foundry - Main JavaScript
 * Handles smooth scrolling, copy buttons, and analytics
 */

(function() {
  'use strict';

  /**
   * Smooth scroll to anchor links
   */
  function initSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');

    links.forEach(link => {
      link.addEventListener('click', function(e) {
        const href = this.getAttribute('href');

        // Ignore empty or just-hash hrefs
        if (href === '#' || href === '') {
          e.preventDefault();
          return;
        }

        const target = document.querySelector(href);

        if (target) {
          e.preventDefault();

          const headerOffset = 80; // Account for fixed header
          const targetPosition = target.offsetTop - headerOffset;

          window.scrollTo({
            top: targetPosition,
            behavior: 'smooth'
          });

          // Update URL without triggering scroll
          history.pushState(null, null, href);

          // Focus target for accessibility
          target.setAttribute('tabindex', '-1');
          target.focus();
        }
      });
    });
  }

  /**
   * Copy to clipboard functionality
   */
  function initCopyButtons() {
    const copyButtons = document.querySelectorAll('.copy-button');

    copyButtons.forEach(button => {
      button.addEventListener('click', async function() {
        const codeBlock = this.closest('.code-block');
        const code = codeBlock.querySelector('code');

        try {
          await navigator.clipboard.writeText(code.textContent);

          // Visual feedback
          const originalHTML = this.innerHTML;
          this.innerHTML = '<svg><!-- Checkmark icon --></svg>';
          this.classList.add('copied');

          setTimeout(() => {
            this.innerHTML = originalHTML;
            this.classList.remove('copied');
          }, 2000);

        } catch (err) {
          console.error('Failed to copy:', err);
        }
      });
    });
  }

  /**
   * Intersection Observer for scroll animations
   */
  function initScrollAnimations() {
    const animatedElements = document.querySelectorAll('.animate-on-scroll');

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              entry.target.classList.add('visible');
              observer.unobserve(entry.target);
            }
          });
        },
        {
          threshold: 0.1,
          rootMargin: '0px 0px -50px 0px'
        }
      );

      animatedElements.forEach(el => observer.observe(el));
    } else {
      // Fallback: show all elements immediately
      animatedElements.forEach(el => el.classList.add('visible'));
    }
  }

  /**
   * Track outbound links (for analytics)
   */
  function trackOutboundLinks() {
    const outboundLinks = document.querySelectorAll('a[target="_blank"]');

    outboundLinks.forEach(link => {
      link.addEventListener('click', function() {
        const url = this.href;

        // Send to analytics if available
        if (typeof gtag !== 'undefined') {
          gtag('event', 'click', {
            'event_category': 'Outbound Link',
            'event_label': url
          });
        }
      });
    });
  }

  /**
   * Add security attributes to external links
   */
  function secureExternalLinks() {
    const externalLinks = document.querySelectorAll('a[target="_blank"]');

    externalLinks.forEach(link => {
      // Prevent tabnabbing
      if (!link.hasAttribute('rel')) {
        link.setAttribute('rel', 'noopener noreferrer');
      }
    });
  }

  /**
   * Initialize all functionality when DOM is ready
   */
  function init() {
    initSmoothScroll();
    initCopyButtons();
    initScrollAnimations();
    trackOutboundLinks();
    secureExternalLinks();

    console.log('Context Foundry initialized ✓');
  }

  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
```

### Performance Optimizations

1. **Lazy Loading Images**
   ```html
   <img src="image.jpg" loading="lazy" alt="Description">
   ```

2. **Defer JavaScript**
   ```html
   <script src="/js/main.js" defer></script>
   ```

3. **Preload Critical Assets**
   ```html
   <link rel="preload" href="/css/variables.css" as="style">
   ```

4. **Minimize Repaints/Reflows**
   - Use CSS transforms instead of position changes
   - Batch DOM reads/writes
   - Use `will-change` for animated elements

5. **Debounce Scroll/Resize Handlers**
   ```javascript
   function debounce(func, wait) {
     let timeout;
     return function executedFunction(...args) {
       clearTimeout(timeout);
       timeout = setTimeout(() => func(...args), wait);
     };
   }
   ```

---

## Content Structure

### Hero Section Content

**Headline**: "Build Complete Software While You Sleep"

**Subheadline**: "AI that autonomously codes, tests, and deploys—from idea to GitHub in 7-15 minutes"

**Primary CTA**: "Get Started" (links to #quick-start)

**Secondary CTA**: "View on GitHub" (links to GitHub repo)

**Value Proposition** (subtle text below CTAs):
- "No babysitting required"
- "Walk away and come back to production-ready code"

### Features Section Content

**Section Title**: "Why Context Foundry?"

**Section Subtitle**: "The only AI that truly works autonomously. Walk away and come back to production-ready software."

**Feature 1: Autonomous Build**
- Icon: Robot/automation symbol
- Title: "Autonomous Build"
- Description: "Describe what you want, then walk away. Come back to complete, tested, deployed applications. Zero supervision required."

**Feature 2: Self-Healing Tests**
- Icon: Wrench/repair symbol
- Title: "Self-Healing Tests"
- Description: "Tests fail? Context Foundry automatically fixes them. Up to 3 retry attempts with intelligent debugging and error analysis."

**Feature 3: Parallel Execution**
- Icon: Multiple arrows/parallel lines
- Title: "Parallel Execution"
- Description: "2-8 concurrent builders working simultaneously. 3x faster than sequential builds. True multi-agent coordination."

**Feature 4: Fresh Contexts**
- Icon: Refresh/clean slate symbol
- Title: "Fresh Contexts"
- Description: "Each spawned agent gets a clean 200K token window. No context pollution, no token accumulation, perfect memory."

**Feature 5: Pattern Learning**
- Icon: Brain/learning symbol
- Title: "Pattern Learning"
- Description: "Captures successful patterns automatically. Gets smarter with every build you run. Learns from your preferences."

**Feature 6: Auto-Deploy**
- Icon: Rocket/deploy symbol
- Title: "Auto-Deploy"
- Description: "Automatically creates GitHub repos, commits code, pushes changes. Zero manual deployment steps."

### How It Works Section Content

**Section Title**: "The Autonomous Pipeline"

**Section Subtitle**: "Five specialized agents working in sequence, each with fresh context"

**Stage 1: Scout**
- Number: 1
- Icon: Magnifying glass/search
- Title: "Scout"
- Description: "Researches requirements, analyzes technical constraints, recommends architecture and tech stack"
- Output: "scout-report.md"

**Stage 2: Architect**
- Number: 2
- Icon: Blueprint/drafting
- Title: "Architect"
- Description: "Designs system architecture, file structure, component specifications, testing strategy"
- Output: "architecture.md"

**Stage 3: Builder**
- Number: 3
- Icon: Hammer/construction
- Title: "Builder"
- Description: "Implements code, writes comprehensive tests, creates documentation (parallel execution enabled)"
- Output: "Working software + tests"

**Stage 4: Tester**
- Number: 4
- Icon: Checkmark/validation
- Title: "Tester"
- Description: "Validates functionality, auto-fixes test failures, captures screenshots, ensures quality"
- Output: "All tests passing ✓"

**Stage 5: Deploy**
- Number: 5
- Icon: Upload/cloud
- Title: "Deploy"
- Description: "Creates GitHub repo, commits all changes, pushes to remote, generates documentation"
- Output: "github.com/user/project"

**Meta-MCP Innovation Callout**:
- Headline: "The Breakthrough: Meta-MCP"
- Description: "Context Foundry doesn't just call external tools—it recursively spawns fresh Claude instances. Each agent gets its own clean 200K context window, enabling true autonomous operation."
- Link: "Read the technical breakdown →" (to INNOVATIONS.md)

### Quick Start Section Content

**Section Title**: "Get Started in 3 Steps"

**Section Subtitle**: "Ready to build autonomously? Install takes less than 5 minutes."

**Step 1: Install MCP Server**
```bash
# Clone the repository
git clone https://github.com/context-foundry/context-foundry.git
cd context-foundry

# Install dependencies
pip install -r requirements-mcp.txt
```

**Step 2: Configure Claude Code**
```bash
# Add MCP server to Claude Code
claude mcp add context-foundry \
  --command python \
  --args /path/to/context-foundry/mcp_server.py
```

**Step 3: Build Something Amazing**
```bash
# Just ask naturally in Claude Code
"Build a todo app with React and TypeScript"

# Walk away. Come back to deployed code.
```

**Footer Note**: "Need detailed setup instructions? Check the [Quick Start Guide](link) or [User Guide](link)"

### Metrics Section Content

**Metric 1**: "7-15 min" / "Average Build Time"
**Metric 2**: "200K" / "Fresh Token Windows"
**Metric 3**: "3x" / "Faster with Parallel"
**Metric 4**: "100%" / "Autonomous"

### CTA Section Content

**Headline**: "Ready to Build Autonomously?"

**Subheadline**: "Join developers who ship complete projects while they sleep"

**Primary CTA**: "Get Started Now" (links to #quick-start)

**Secondary CTA**: "Star on GitHub" (links to GitHub)

### Footer Content

**Column 1: Brand**
- Logo + "Context Foundry"
- Tagline: "Build complete software autonomously"

**Column 2: Documentation**
- Quick Start (link)
- User Guide (link)
- Technical Innovations (link)
- Changelog (link)

**Column 3: Resources**
- GitHub Repository (link)
- Report Issues (link)
- Discussions (link)
- MIT License (link)

**Column 4: Connect**
- Twitter/X (link)
- LinkedIn (link)
- Contact (email)

**Copyright Bar**:
- "© 2025 Context Foundry. Open source under MIT License."
- "Version 2.1.0"

### Copy Guidelines

**Tone & Voice**:
- Professional but approachable
- Technical but not jargon-heavy
- Confident but not arrogant
- Focus on benefits, not features

**Key Messages**:
1. **Autonomy**: Emphasize "walk away" capability
2. **Speed**: Highlight 7-15 minute build times
3. **Quality**: Stress self-healing tests and fresh contexts
4. **Innovation**: Explain Meta-MCP breakthrough

**Writing Style**:
- Active voice: "Build X" not "X is built"
- Present tense: "Context Foundry builds" not "will build"
- Short sentences: Max 20 words
- Scannable: Bullet points, short paragraphs
- Action-oriented: Start with verbs

**SEO Keywords** (natural integration):
- Autonomous AI development
- AI coding assistant
- Automated testing
- Claude AI
- MCP server
- GitHub deployment
- Self-healing tests

---

## Testing Requirements

### Browser Testing Matrix

| Browser | Versions | Priority | Test Scope |
|---------|----------|----------|------------|
| Chrome | Latest 2 | P0 | Full functionality |
| Firefox | Latest 2 | P0 | Full functionality |
| Safari | Latest 2 (iOS + macOS) | P0 | Full functionality |
| Edge | Latest 2 | P1 | Core functionality |
| Chrome Android | Latest | P1 | Mobile responsive |
| Safari iOS | Latest 2 | P0 | Mobile responsive |

### Device Testing Matrix

| Device Type | Viewport Size | Priority | Test Cases |
|-------------|---------------|----------|------------|
| Mobile Small | 320px × 568px (iPhone SE) | P0 | Layout, navigation, CTAs |
| Mobile Medium | 375px × 667px (iPhone 8) | P0 | All features |
| Mobile Large | 414px × 896px (iPhone 11) | P1 | All features |
| Tablet Portrait | 768px × 1024px (iPad) | P1 | Responsive grid |
| Tablet Landscape | 1024px × 768px | P1 | Desktop layout |
| Desktop Small | 1280px × 720px | P0 | Full desktop experience |
| Desktop Large | 1920px × 1080px | P1 | Wide screen layout |
| Desktop Wide | 2560px × 1440px | P2 | Max width constraints |

### Functional Test Cases

#### Navigation Tests
1. **Mobile Menu Toggle**
   - Click hamburger icon → menu slides in
   - Click link → menu closes
   - Click outside → menu closes
   - Press Escape → menu closes
   - Resize to desktop → menu auto-closes if open

2. **Smooth Scroll**
   - Click nav link → scrolls to section smoothly
   - Click CTA → scrolls to Quick Start section
   - URL updates without page jump

3. **External Links**
   - All GitHub links open in new tab
   - All external links have rel="noopener noreferrer"

#### Content Tests
1. **Code Copy Buttons**
   - Hover over code block → copy button appears
   - Click copy → text copied to clipboard
   - Button shows checkmark for 2 seconds
   - Works on all code blocks

2. **CTA Buttons**
   - Primary CTA scrolls to Quick Start
   - Secondary CTA opens GitHub in new tab
   - Hover states work correctly
   - Focus states visible for keyboard navigation

3. **Responsive Images**
   - Hero background loads correctly
   - Logo renders at correct size
   - No broken images

#### Accessibility Tests
1. **Keyboard Navigation**
   - Tab through all interactive elements
   - Focus indicators visible
   - Skip to main content link (optional)
   - No keyboard traps

2. **Screen Reader**
   - ARIA labels on buttons
   - Alt text on images
   - Semantic HTML structure
   - Proper heading hierarchy (h1 → h2 → h3)

3. **Color Contrast**
   - Text meets WCAG AA (4.5:1 for normal, 3:1 for large)
   - Buttons meet contrast requirements
   - Links distinguishable from body text

### Performance Tests

#### Lighthouse Audit Targets
- **Performance**: ≥ 90
- **Accessibility**: ≥ 95
- **Best Practices**: ≥ 95
- **SEO**: 100

#### Core Web Vitals
- **LCP (Largest Contentful Paint)**: < 2.5s
- **FID (First Input Delay)**: < 100ms
- **CLS (Cumulative Layout Shift)**: < 0.1

#### Load Time Tests
- **Desktop (4G)**: < 1.5s
- **Mobile (3G)**: < 3s
- **Time to Interactive**: < 2s
- **Total Page Size**: < 500KB (uncompressed)

### Visual Regression Tests (Optional)

**Tool**: BackstopJS or Percy

**Test Scenarios**:
1. Homepage - Desktop (1280px)
2. Homepage - Tablet (768px)
3. Homepage - Mobile (375px)
4. Mobile menu open
5. Hover states on buttons
6. Focus states on interactive elements

### SEO Validation

1. **HTML Validation**
   - Run through W3C validator
   - Zero errors, minimal warnings

2. **Meta Tags**
   - Title length: 50-60 characters
   - Description length: 150-160 characters
   - Open Graph tags present
   - Twitter Card tags present

3. **Structured Data**
   - JSON-LD validates via Google's tool
   - Schema.org markup correct

4. **Robots & Sitemap**
   - robots.txt allows indexing
   - Canonical URL set correctly

### Browser-Based Manual Testing Checklist

**Priority 0 (Must Pass)**:
- [ ] Hero section displays correctly on mobile/desktop
- [ ] Mobile navigation opens/closes smoothly
- [ ] All CTAs are clickable and navigate correctly
- [ ] Code blocks display with proper syntax highlighting
- [ ] Copy buttons work and provide feedback
- [ ] Smooth scroll works on all anchor links
- [ ] No console errors or warnings
- [ ] Page loads in < 3s on 3G
- [ ] All images load without errors
- [ ] Footer links work

**Priority 1 (Should Pass)**:
- [ ] Animations play smoothly (no jank)
- [ ] Hover states work on all interactive elements
- [ ] Focus states visible for keyboard users
- [ ] Resize window → layout adapts correctly
- [ ] External links open in new tabs
- [ ] No horizontal scroll on mobile
- [ ] Typography scales properly at all breakpoints

**Priority 2 (Nice to Pass)**:
- [ ] Gradient text animates smoothly
- [ ] Glow effects on CTAs
- [ ] Intersection Observer animations trigger
- [ ] Back button works correctly
- [ ] Print stylesheet (if implemented)

### Test Execution Plan

**Phase 1: Development Testing** (During Build)
1. Test in Chrome DevTools device mode
2. Validate HTML with W3C
3. Check console for errors
4. Test all interactive features

**Phase 2: Cross-Browser Testing** (After Initial Build)
1. Test in Chrome, Firefox, Safari
2. Test on real iOS device
3. Test on real Android device
4. Fix any browser-specific bugs

**Phase 3: Performance Testing** (Before Launch)
1. Run Lighthouse audit
2. Test on simulated 3G connection
3. Optimize images if needed
4. Minify CSS/JS if needed

**Phase 4: Accessibility Testing** (Before Launch)
1. Keyboard navigation test
2. Screen reader test (NVDA or VoiceOver)
3. Color contrast checker
4. WAVE accessibility tool

**Phase 5: Final QA** (Pre-Launch)
1. Complete manual testing checklist
2. Test all links (internal and external)
3. Verify SEO meta tags
4. Test social media preview cards
5. Final Lighthouse audit

### Success Criteria

**Launch Blockers** (must be fixed):
- Any P0 test failure
- Lighthouse Performance < 85
- Lighthouse Accessibility < 90
- Critical layout issues on mobile
- Broken navigation
- Non-functional CTAs

**Nice to Fix** (can launch without):
- P2 test failures
- Minor animation glitches
- Optional features
- Edge case browser issues

### Bug Reporting Template

```markdown
**Bug Title**: [Short description]

**Priority**: P0 / P1 / P2

**Environment**:
- Browser: [Chrome 120]
- Device: [iPhone 12]
- Viewport: [375x812]

**Steps to Reproduce**:
1. Navigate to [URL]
2. Click on [element]
3. Observe [behavior]

**Expected Behavior**:
[What should happen]

**Actual Behavior**:
[What actually happens]

**Screenshots/Video**:
[Attach visual evidence]

**Console Errors**:
[Paste any errors]
```

---

## Step-by-Step Implementation Plan

### Overview

**Total Estimated Time**: 4-5 hours

**Team Size**: 1-2 developers

**Prerequisites**:
- Git repository initialized
- Basic understanding of HTML/CSS/JS
- Text editor or IDE
- Modern web browser for testing

---

### Phase 1: Project Setup (15 minutes)

**Goal**: Create directory structure and boilerplate files

**Steps**:

1. **Create directory structure**
   ```bash
   cd /home/chuck/homelab/context-foundry/public
   mkdir -p css js images
   ```

2. **Create placeholder files**
   ```bash
   touch index.html
   touch css/reset.css css/variables.css css/styles.css
   touch js/navigation.js js/main.js
   touch robots.txt
   ```

3. **Initialize git (if not already done)**
   ```bash
   git init
   git add .
   git commit -m "Initial project structure"
   ```

**Deliverables**:
- [ ] Directory structure created
- [ ] All files exist (empty but present)
- [ ] Git repository initialized

**Dependencies**: None

**Estimated Time**: 15 minutes

---

### Phase 2: CSS Foundation (45 minutes)

**Goal**: Establish design system and base styles

**Steps**:

1. **Create reset.css** (5 minutes)
   - Modern CSS reset
   - Box-sizing border-box
   - Remove default margins/padding
   - Set default font smoothing

2. **Create variables.css** (20 minutes)
   - Define all CSS custom properties:
     - Color palette (primary, secondary, backgrounds, text)
     - Typography scale (font sizes, weights, families)
     - Spacing scale (8px base unit)
     - Border radius values
     - Shadow values
     - Transition timings
     - Breakpoints (as comments)

3. **Create base styles in styles.css** (20 minutes)
   - Body and html defaults
   - Typography base styles (headings, paragraphs, links)
   - Container system
   - Section utilities
   - Button base styles
   - Focus states for accessibility

**Deliverables**:
- [ ] reset.css complete
- [ ] variables.css with all design tokens
- [ ] styles.css with base styles
- [ ] System fonts loading correctly

**Dependencies**: Phase 1 complete

**Estimated Time**: 45 minutes

**Testing**:
- Create a simple HTML file with all element types
- Verify colors, typography, spacing render correctly
- Check in browser DevTools

---

### Phase 3: HTML Structure (60 minutes)

**Goal**: Build complete semantic HTML structure

**Steps**:

1. **Document head** (10 minutes)
   - DOCTYPE and html tag
   - Meta tags (charset, viewport, description)
   - Open Graph tags
   - Twitter Card tags
   - Link to stylesheets
   - Favicon reference

2. **Header/Navigation** (15 minutes)
   - Logo and brand name
   - Desktop navigation links
   - Mobile hamburger button
   - Proper ARIA labels

3. **Hero Section** (10 minutes)
   - Main headline with gradient span
   - Subheadline
   - CTA button group
   - Scroll indicator
   - Background decoration container

4. **Features Section** (10 minutes)
   - Section header (title + subtitle)
   - Features grid container
   - 6 feature cards (icon, title, description)

5. **How It Works Section** (10 minutes)
   - Section header
   - Pipeline flow container
   - 5 stage cards with connectors
   - Meta-MCP callout box

6. **Quick Start Section** (10 minutes)
   - Section header
   - 3 step cards
   - Code blocks with copy buttons
   - Footer note with links

7. **Metrics Section** (5 minutes)
   - 4 metric cards (value + label)

8. **CTA Section** (5 minutes)
   - Headline and subheadline
   - Button group

9. **Footer** (10 minutes)
   - 4-column grid
   - Brand, Documentation, Resources, Connect
   - Copyright bar

10. **Script tags** (5 minutes)
    - Link to JavaScript files with defer attribute

**Deliverables**:
- [ ] Complete index.html with all sections
- [ ] Semantic HTML5 elements used correctly
- [ ] All accessibility attributes present
- [ ] Content placeholders in place

**Dependencies**: Phase 2 complete (CSS foundation)

**Estimated Time**: 60 minutes

**Testing**:
- Validate HTML with W3C validator
- Check heading hierarchy (h1 → h2 → h3)
- Verify all ARIA labels present
- Test keyboard navigation (tab through elements)

---

### Phase 4: Component Styling (90 minutes)

**Goal**: Style all components with responsive design

**Steps**:

1. **Header/Navigation styling** (20 minutes)
   - Fixed header with backdrop blur
   - Logo and text alignment
   - Desktop navigation (horizontal flexbox)
   - Mobile hamburger icon (3 lines)
   - Mobile menu (slide-in drawer)
   - Responsive breakpoints
   - Hover and focus states

2. **Hero Section styling** (15 minutes)
   - Full viewport height
   - Centered content
   - Gradient text effect
   - Button group layout
   - Scroll indicator animation
   - Background gradient overlay

3. **Features Section styling** (15 minutes)
   - Section header centered
   - CSS Grid (1 column mobile, 2 tablet, 3 desktop)
   - Feature card styling (background, border, padding)
   - Icon sizing and color
   - Hover effects (lift + glow)

4. **Pipeline Section styling** (15 minutes)
   - Pipeline flow (vertical mobile, horizontal desktop)
   - Stage cards with numbers
   - Connector arrows (hide on mobile)
   - Stage output badges
   - Innovation callout box styling

5. **Quick Start Section styling** (15 minutes)
   - Step cards with number badges
   - Code block styling (dark background, borders)
   - Syntax highlighting classes
   - Copy button positioning and states
   - Footer note styling

6. **Metrics Section styling** (5 minutes)
   - Grid layout (2x2 mobile, 4x1 desktop)
   - Large metric values
   - Subtle card backgrounds

7. **CTA Section styling** (5 minutes)
   - Centered content
   - Large button group
   - Emphasis on primary CTA

8. **Footer styling** (10 minutes)
   - 4-column grid (1 mobile, 2 tablet, 4 desktop)
   - Link styles
   - Copyright bar (flexbox)

**Deliverables**:
- [ ] All components styled
- [ ] Responsive at all breakpoints (320px, 768px, 1024px, 1440px)
- [ ] Hover and focus states working
- [ ] Animations smooth (no jank)

**Dependencies**: Phase 3 complete (HTML structure)

**Estimated Time**: 90 minutes

**Testing**:
- Test in Chrome DevTools device mode
- Resize browser from 320px to 1920px
- Verify no horizontal scroll on mobile
- Check hover states on desktop
- Verify focus states with keyboard navigation

---

### Phase 5: JavaScript Implementation (45 minutes)

**Goal**: Add interactivity and progressive enhancements

**Steps**:

1. **navigation.js - Mobile menu** (20 minutes)
   - Query DOM elements
   - Toggle menu function
   - Close menu function
   - Outside click handler
   - Escape key handler
   - Body scroll lock/unlock
   - Resize handler
   - ARIA attribute updates

2. **main.js - Core functionality** (25 minutes)
   - Smooth scroll to anchor links
   - Copy to clipboard for code blocks
   - Intersection Observer for scroll animations
   - Outbound link tracking (analytics hooks)
   - External link security (noopener/noreferrer)
   - Initialize all functions on DOM ready

**Deliverables**:
- [ ] navigation.js complete and working
- [ ] main.js complete and working
- [ ] Mobile menu toggles smoothly
- [ ] Smooth scroll works
- [ ] Copy buttons functional
- [ ] No console errors

**Dependencies**: Phase 4 complete (component styling)

**Estimated Time**: 45 minutes

**Testing**:
- Click hamburger → menu opens
- Click outside → menu closes
- Press Escape → menu closes
- Click nav link → smooth scroll to section
- Hover code block → copy button appears
- Click copy → clipboard updated, checkmark shown
- Verify no JavaScript errors in console

---

### Phase 6: Content Population (45 minutes)

**Goal**: Replace placeholders with actual content

**Steps**:

1. **Hero section content** (5 minutes)
   - Update headline and subheadline
   - Verify CTA links

2. **Features section content** (10 minutes)
   - Write all 6 feature descriptions
   - Ensure consistent tone and length

3. **Pipeline section content** (10 minutes)
   - Write all 5 stage descriptions
   - Add Meta-MCP explanation

4. **Quick Start section content** (10 minutes)
   - Add real installation commands
   - Verify code syntax
   - Add proper comments in code

5. **Footer content** (5 minutes)
   - Add all links (verify they work)
   - Update copyright year
   - Add version number

6. **Meta tags** (5 minutes)
   - Update title and description
   - Verify character counts
   - Update Open Graph tags

**Deliverables**:
- [ ] All content replaced with final copy
- [ ] Code examples accurate
- [ ] All links point to correct URLs
- [ ] Meta tags optimized for SEO

**Dependencies**: Phase 5 complete (JavaScript)

**Estimated Time**: 45 minutes

**Testing**:
- Read through entire page for typos
- Click every link to verify it works
- Check code examples for accuracy
- Verify external links open in new tabs

---

### Phase 7: Assets & Icons (30 minutes)

**Goal**: Create and add visual assets

**Steps**:

1. **Create logo.svg** (10 minutes)
   - Design simple, recognizable mark
   - Export as optimized SVG
   - Test at different sizes

2. **Create hero-gradient.svg** (5 minutes)
   - Decorative gradient background
   - Subtle, not distracting

3. **Create og-image.png** (10 minutes)
   - 1200 × 630px social preview
   - Include logo, tagline, URL
   - Test on Facebook/Twitter preview tools

4. **Create favicon.ico** (5 minutes)
   - 32×32 icon from logo
   - Test in browser tab

**Deliverables**:
- [ ] logo.svg created and optimized
- [ ] hero-gradient.svg created
- [ ] og-image.png created (1200×630)
- [ ] favicon.ico created
- [ ] All assets under 200KB total

**Dependencies**: Phase 6 complete (content)

**Estimated Time**: 30 minutes

**Testing**:
- Verify logo renders correctly at all sizes
- Check favicon shows in browser tab
- Test social preview on Facebook/Twitter card validators
- Ensure no broken image links

---

### Phase 8: Testing & QA (60 minutes)

**Goal**: Comprehensive testing across devices and browsers

**Steps**:

1. **HTML Validation** (5 minutes)
   - Run through W3C validator
   - Fix any errors or warnings

2. **Cross-Browser Testing** (20 minutes)
   - Chrome (latest)
   - Firefox (latest)
   - Safari (macOS/iOS)
   - Edge (latest)
   - Fix browser-specific issues

3. **Responsive Testing** (15 minutes)
   - Test at 320px (iPhone SE)
   - Test at 375px (iPhone 8)
   - Test at 768px (iPad portrait)
   - Test at 1024px (iPad landscape)
   - Test at 1440px (desktop)
   - Fix layout issues

4. **Accessibility Testing** (10 minutes)
   - Keyboard navigation (tab through all elements)
   - Screen reader test (VoiceOver or NVDA)
   - Color contrast check
   - WAVE accessibility tool

5. **Performance Testing** (10 minutes)
   - Run Lighthouse audit
   - Target: Performance ≥ 90
   - Fix any critical issues
   - Optimize images if needed

**Deliverables**:
- [ ] HTML validates with zero errors
- [ ] Works in all major browsers
- [ ] Responsive at all breakpoints
- [ ] Keyboard navigation works
- [ ] Lighthouse Performance ≥ 90
- [ ] Lighthouse Accessibility ≥ 95

**Dependencies**: Phase 7 complete (assets)

**Estimated Time**: 60 minutes

**Testing Matrix**:
| Test | Pass/Fail | Notes |
|------|-----------|-------|
| W3C Validation | | |
| Chrome Desktop | | |
| Firefox Desktop | | |
| Safari macOS | | |
| Safari iOS | | |
| Chrome Android | | |
| Responsive (320px) | | |
| Responsive (768px) | | |
| Responsive (1024px) | | |
| Keyboard Navigation | | |
| Lighthouse Performance | | |
| Lighthouse Accessibility | | |

---

### Phase 9: Optimization & Polish (30 minutes)

**Goal**: Final optimizations and refinements

**Steps**:

1. **Image Optimization** (10 minutes)
   - Compress PNG images
   - Optimize SVGs (remove unnecessary code)
   - Add width/height attributes

2. **CSS Cleanup** (10 minutes)
   - Remove unused styles
   - Organize properties alphabetically
   - Add comments for complex sections
   - Verify no duplicate rules

3. **JavaScript Cleanup** (5 minutes)
   - Remove console.logs
   - Add JSDoc comments
   - Verify no unused functions

4. **Final Review** (5 minutes)
   - Check all content for typos
   - Verify all links work
   - Test all interactive features
   - Review in browser DevTools

**Deliverables**:
- [ ] Images optimized (WebP or compressed PNG)
- [ ] CSS organized and commented
- [ ] JavaScript clean and documented
- [ ] Final QA checklist complete

**Dependencies**: Phase 8 complete (testing)

**Estimated Time**: 30 minutes

**Testing**:
- Run Lighthouse one more time
- Check total page size (should be < 500KB)
- Verify load time on simulated 3G

---

### Phase 10: Deployment Preparation (15 minutes)

**Goal**: Prepare for production deployment

**Steps**:

1. **Create robots.txt** (2 minutes)
   ```
   User-agent: *
   Allow: /

   Sitemap: https://contextfoundry.dev/sitemap.xml
   ```

2. **Add Google Analytics (optional)** (5 minutes)
   - Add GA4 tracking code to index.html
   - Test events fire correctly

3. **Final git commit** (3 minutes)
   ```bash
   git add .
   git commit -m "Complete Context Foundry marketing site v1.0"
   git tag v1.0.0
   ```

4. **Deployment documentation** (5 minutes)
   - Create deployment guide (README.md)
   - Document environment requirements
   - Add deployment commands

**Deliverables**:
- [ ] robots.txt created
- [ ] Analytics added (optional)
- [ ] All changes committed to git
- [ ] Deployment docs written

**Dependencies**: Phase 9 complete (optimization)

**Estimated Time**: 15 minutes

---

## Implementation Dependencies Graph

```
Phase 1 (Setup)
    ↓
Phase 2 (CSS Foundation)
    ↓
Phase 3 (HTML Structure)
    ↓
Phase 4 (Component Styling) ←→ Phase 5 (JavaScript)
    ↓                              ↓
Phase 6 (Content Population)
    ↓
Phase 7 (Assets & Icons)
    ↓
Phase 8 (Testing & QA)
    ↓
Phase 9 (Optimization)
    ↓
Phase 10 (Deployment)
```

---

## Quick Reference Checklist

### Pre-Launch Checklist

**Content**:
- [ ] All placeholder text replaced
- [ ] No Lorem Ipsum remaining
- [ ] All code examples tested
- [ ] All links verified (no 404s)
- [ ] Spelling/grammar checked

**Design**:
- [ ] Consistent spacing throughout
- [ ] Color contrast meets WCAG AA
- [ ] Typography hierarchy clear
- [ ] Hover states on all interactive elements
- [ ] Focus states visible

**Functionality**:
- [ ] Mobile navigation works
- [ ] Smooth scroll works
- [ ] Copy buttons work
- [ ] All CTAs clickable
- [ ] External links open in new tabs

**Performance**:
- [ ] Images optimized
- [ ] CSS/JS minified (optional)
- [ ] Lighthouse Performance ≥ 90
- [ ] Load time < 3s on 3G

**SEO**:
- [ ] Title optimized (50-60 chars)
- [ ] Meta description optimized (150-160 chars)
- [ ] Open Graph tags present
- [ ] Twitter Card tags present
- [ ] Structured data (JSON-LD) added
- [ ] robots.txt created
- [ ] Favicon present

**Accessibility**:
- [ ] Semantic HTML used
- [ ] ARIA labels present
- [ ] Keyboard navigation works
- [ ] Screen reader tested
- [ ] Color contrast validated
- [ ] Lighthouse Accessibility ≥ 95

**Cross-Browser**:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] iOS Safari
- [ ] Chrome Android

**Responsive**:
- [ ] 320px (mobile small)
- [ ] 375px (mobile medium)
- [ ] 768px (tablet)
- [ ] 1024px (desktop)
- [ ] 1440px+ (wide)

---

## Troubleshooting Guide

### Common Issues

**Issue: Mobile menu doesn't close when clicking outside**
- **Cause**: Event listener not attached correctly
- **Fix**: Check `handleOutsideClick` function in navigation.js
- **Test**: Click outside menu area

**Issue: Smooth scroll jerky or not working**
- **Cause**: Missing `scroll-behavior: smooth` or JS conflict
- **Fix**: Add CSS `scroll-behavior: smooth` to html element
- **Test**: Click nav links and observe scroll

**Issue: Copy button doesn't work**
- **Cause**: Clipboard API not supported or HTTPS required
- **Fix**: Check for HTTPS (required for clipboard API)
- **Test**: Click copy button, paste into editor

**Issue: Layout breaks at certain viewport widths**
- **Cause**: Missing responsive breakpoint or overflow
- **Fix**: Add media query for that breakpoint
- **Test**: Resize browser slowly from 320px to 1920px

**Issue: Images don't load**
- **Cause**: Wrong file path or missing alt attribute
- **Fix**: Verify image paths relative to index.html
- **Test**: Check browser DevTools Network tab

**Issue: Lighthouse score low**
- **Cause**: Large images, render-blocking resources, or missing optimization
- **Fix**: Optimize images, defer JS, inline critical CSS
- **Test**: Run Lighthouse audit, check recommendations

---

## Success Metrics

### Launch Day Targets

**Performance**:
- Lighthouse Performance: ≥ 90
- Lighthouse Accessibility: ≥ 95
- Lighthouse Best Practices: ≥ 95
- Lighthouse SEO: 100
- Load time (3G): < 3 seconds
- Total page size: < 500KB

**Functionality**:
- Zero console errors
- All links working (0 broken links)
- Mobile navigation smooth
- All CTAs clickable

**Quality**:
- W3C HTML validation: 0 errors
- Cross-browser tested: All major browsers
- Responsive tested: 5+ breakpoints
- Accessibility: WCAG AA compliant

---

## Post-Launch Monitoring

### Week 1 Metrics to Track

1. **Performance**:
   - Average load time
   - Bounce rate
   - Time on page

2. **Engagement**:
   - CTA click-through rate
   - GitHub link clicks
   - Quick Start section views

3. **Technical**:
   - JavaScript errors (analytics)
   - Browser breakdown
   - Device breakdown
   - Geographic distribution

4. **SEO**:
   - Organic search impressions
   - Click-through rate from search
   - Average ranking position

---

## Architecture Complete

This architecture specification provides everything needed to build the Context Foundry marketing website. Builders can follow this document step-by-step to implement a production-ready, performant, accessible, and SEO-optimized static site.

**Key Deliverables**:
✓ Complete file structure
✓ HTML component specifications
✓ CSS design system
✓ JavaScript functionality specs
✓ Content structure and guidelines
✓ Comprehensive testing requirements
✓ Step-by-step implementation plan

**Total Estimated Time**: 4-5 hours
**Complexity**: Medium
**Risk Level**: Low

Ready for Builder phase.
