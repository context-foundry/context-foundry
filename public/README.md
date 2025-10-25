# Context Foundry Marketing Website

Professional marketing and documentation website for Context Foundry - autonomous AI development platform.

## 🌐 Live Site

**URL**: https://contextfoundry.dev

## 📋 Overview

This is a static HTML/CSS/JavaScript marketing website showcasing Context Foundry's autonomous development capabilities. The site is designed to be fast, accessible, and SEO-optimized with zero build dependencies.

## ✨ Features

- **Zero Dependencies**: Pure HTML/CSS/JavaScript (no frameworks, no build process)
- **Responsive Design**: Mobile-first approach, works on all devices (320px - 2560px)
- **Fast Performance**: < 3 second load time, optimized assets
- **SEO Optimized**: Complete meta tags, Open Graph, Twitter Cards
- **Accessible**: WCAG 2.1 AA compliant, semantic HTML, ARIA labels
- **Modern Styling**: CSS custom properties, flexbox, grid, smooth animations

## 🗂️ Project Structure

```
public/
├── index.html              # Main landing page
├── css/
│   ├── reset.css          # Browser normalization
│   ├── variables.css      # Design tokens (colors, spacing, typography)
│   └── styles.css         # Main stylesheet
├── js/
│   ├── navigation.js      # Mobile menu toggle
│   └── main.js            # Core functionality (smooth scroll, copy buttons)
├── images/
│   ├── logo.svg           # Context Foundry logo (to be added)
│   ├── hero-gradient.svg  # Hero background (to be added)
│   └── og-image.png       # Social preview image (to be added)
├── robots.txt             # SEO crawler instructions
└── README.md              # This file
```

## 🎨 Design System

### Colors

- **Primary**: Electric cyan (#00d9ff) - CTAs, links, accents
- **Secondary**: Bright green (#00ff00) - Success, code highlights
- **Accent**: Magenta (#ff00ff) / Purple (#a855f7) - Gradients
- **Background**: Deep black (#0a0a0a) - Primary background
- **Text**: White (#ffffff) / Gray shades - Typography

### Typography

- **Sans-serif**: System font stack (optimized for each OS)
- **Monospace**: Monaco, Menlo - Code blocks
- **Fluid scaling**: Responsive font sizes using clamp()

### Spacing

- **Base unit**: 8px
- **Scale**: 0.5rem (8px) to 8rem (128px)

## 🚀 Local Development

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/context-foundry/context-foundry.git
   cd context-foundry/public
   ```

2. **Serve locally** (choose one):

   **Option A: Python**
   ```bash
   python3 -m http.server 8000
   ```

   **Option B: Node.js**
   ```bash
   npx http-server -p 8000
   ```

   **Option C: PHP**
   ```bash
   php -S localhost:8000
   ```

3. **Open in browser**:
   ```
   http://localhost:8000
   ```

### Live Reload (Optional)

For development with live reload:

```bash
npx live-server --port=8000
```

## 📝 Content Sections

1. **Hero Section**: Compelling headline, CTA buttons
2. **Features**: 6 key features (autonomous, self-healing, parallel, etc.)
3. **How It Works**: 5-stage pipeline visualization
4. **Quick Start**: 3-step installation guide
5. **Metrics**: Key statistics (build time, performance)
6. **CTA**: Final call-to-action
7. **Footer**: Links, documentation, resources

## 🧪 Testing

### Browser Testing

Test on the following browsers:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest, macOS/iOS)

### Responsive Testing

Test at these breakpoints:
- Mobile: 320px, 375px, 414px
- Tablet: 768px, 1024px
- Desktop: 1280px, 1440px, 1920px

### Manual Testing Checklist

- [ ] Mobile menu opens/closes correctly
- [ ] Smooth scrolling works on all anchor links
- [ ] Copy buttons work in code blocks
- [ ] All external links open in new tab
- [ ] Images load (when added)
- [ ] No horizontal scroll on mobile
- [ ] Hover states work on desktop
- [ ] Focus states visible for keyboard navigation

### Validation

**HTML Validation**:
```bash
# Using W3C validator
curl -s -F "out=gnu" -F "file=@index.html" https://validator.w3.org/check
```

**Lighthouse Audit**:
```bash
# Using Chrome DevTools or:
npx lighthouse https://contextfoundry.dev --view
```

**Target Scores**:
- Performance: ≥ 90
- Accessibility: ≥ 95
- Best Practices: ≥ 95
- SEO: 100

## 🎯 Performance Targets

- **First Contentful Paint (FCP)**: < 1.5s
- **Largest Contentful Paint (LCP)**: < 2.5s
- **Time to Interactive (TTI)**: < 3.0s
- **Total Page Size**: < 500KB
- **Total Requests**: < 15

## 📦 Deployment

### GitHub Pages

1. Push to `main` branch
2. Enable GitHub Pages in repository settings
3. Select source: `main` branch, `/public` folder
4. Custom domain: `contextfoundry.dev`

### Custom Domain Setup

1. Add CNAME file:
   ```bash
   echo "contextfoundry.dev" > CNAME
   ```

2. Configure DNS:
   ```
   A Record:    @ → 185.199.108.153
   A Record:    @ → 185.199.109.153
   A Record:    @ → 185.199.110.153
   A Record:    @ → 185.199.111.153
   CNAME:       www → context-foundry.github.io
   ```

3. Enable HTTPS in GitHub Pages settings

## 🔧 Maintenance

### Adding Images

1. Create assets:
   - `images/logo.svg`: 200x40px SVG logo
   - `images/hero-gradient.svg`: Abstract gradient background
   - `images/og-image.png`: 1200x630px social preview

2. Update references in `index.html` if needed

### Updating Content

1. **Text content**: Edit `index.html` directly
2. **Styling**: Modify `css/styles.css`
3. **Behavior**: Update `js/main.js` or `js/navigation.js`
4. **Design tokens**: Change variables in `css/variables.css`

## 📄 License

MIT License - see [LICENSE](../LICENSE) for details

## 🤖 Built With

- **HTML5**: Semantic markup
- **CSS3**: Custom properties, flexbox, grid
- **Vanilla JavaScript**: No frameworks
- **Love**: And a lot of coffee ☕

## 🙏 Credits

**Built autonomously by Context Foundry**

This marketing website was created by Context Foundry itself, demonstrating the platform's capability to build complete, production-ready projects autonomously.

---

**Version**: 1.0.0
**Last Updated**: 2025-01-13
**Maintainer**: Context Foundry Team
