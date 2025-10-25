# Deployment Guide

Guide for deploying the Context Foundry marketing website to production.

## Deployment Options

### Option 1: GitHub Pages (Recommended)

**Advantages**:
- Free hosting
- Automatic HTTPS
- CDN included
- Easy custom domain setup
- CI/CD integration

**Steps**:

1. **Push to GitHub**:
   ```bash
   cd /home/chuck/homelab/context-foundry/public
   git init
   git add .
   git commit -m "Initial commit: Context Foundry marketing website"
   git remote add origin https://github.com/context-foundry/contextfoundry.dev.git
   git push -u origin main
   ```

2. **Enable GitHub Pages**:
   - Go to repository Settings
   - Navigate to Pages section
   - Source: Deploy from branch
   - Branch: `main` / `/` (root)
   - Click Save

3. **Configure Custom Domain**:
   - Add file `CNAME` with content: `contextfoundry.dev`
   - Configure DNS (see DNS Configuration below)
   - Enable "Enforce HTTPS" in GitHub Pages settings

4. **Verify Deployment**:
   - Wait 1-2 minutes for build
   - Visit `https://context-foundry.github.io`
   - Visit `https://contextfoundry.dev` (after DNS propagation)

---

### Option 2: Netlify

**Advantages**:
- Instant cache invalidation
- Form handling (if needed later)
- Split testing (A/B tests)
- Edge functions support

**Steps**:

1. **Connect Repository**:
   - Sign up at netlify.com
   - Click "New site from Git"
   - Select GitHub repository

2. **Build Settings**:
   - Build command: (leave empty - static site)
   - Publish directory: `/` or `public`
   - Click "Deploy site"

3. **Custom Domain**:
   - Site settings → Domain management
   - Add custom domain: `contextfoundry.dev`
   - Follow DNS configuration instructions

---

### Option 3: Vercel

**Advantages**:
- Edge network
- Analytics included
- Preview deployments
- Fast global CDN

**Steps**:

1. **Import Project**:
   - Sign up at vercel.com
   - Click "Import Project"
   - Connect GitHub repository

2. **Deploy**:
   - Framework Preset: Other
   - Build Command: (leave empty)
   - Output Directory: `./`
   - Click "Deploy"

3. **Custom Domain**:
   - Project Settings → Domains
   - Add domain: `contextfoundry.dev`
   - Configure DNS as instructed

---

## DNS Configuration

### For GitHub Pages

Add these DNS records to your domain registrar:

```
Type    Name    Value                       TTL
A       @       185.199.108.153            3600
A       @       185.199.109.153            3600
A       @       185.199.110.153            3600
A       @       185.199.111.153            3600
CNAME   www     context-foundry.github.io   3600
```

### For Netlify

```
Type    Name    Value                           TTL
A       @       75.2.60.5                      3600
CNAME   www     your-site.netlify.app          3600
```

### For Vercel

```
Type    Name    Value                           TTL
A       @       76.76.21.21                    3600
CNAME   www     cname.vercel-dns.com           3600
```

**DNS Propagation**: Wait 10 minutes to 48 hours (usually < 1 hour)

---

## Pre-Deployment Checklist

### Required

- [x] All HTML/CSS/JS files created
- [x] Tests passed
- [ ] Add images (logo.svg, hero-gradient.svg, og-image.png)
- [ ] Add favicon.ico
- [ ] Update GitHub links (if repository name changed)
- [ ] Verify all links work
- [ ] Test on mobile device

### Recommended

- [ ] Minify CSS and JavaScript
- [ ] Optimize images (compress, convert to WebP)
- [ ] Add sitemap.xml
- [ ] Add Google Analytics or Plausible
- [ ] Set up monitoring (UptimeRobot, Pingdom)

### Optional

- [ ] Add CNAME file for custom domain
- [ ] Configure Content Security Policy (CSP) headers
- [ ] Add security headers (X-Frame-Options, etc.)
- [ ] Set up email for contact form (if added)

---

## Post-Deployment Validation

1. **Verify Live Site**:
   ```bash
   curl -I https://contextfoundry.dev
   # Should return: HTTP/2 200
   ```

2. **Check HTTPS**:
   - Ensure green padlock in browser
   - Certificate should be valid
   - No mixed content warnings

3. **Run Lighthouse Audit**:
   ```bash
   npx lighthouse https://contextfoundry.dev --view
   ```

   **Target Scores**:
   - Performance: ≥ 90
   - Accessibility: ≥ 95
   - Best Practices: ≥ 95
   - SEO: 100

4. **Test Responsiveness**:
   - Chrome DevTools → Device Mode
   - Test on: iPhone, iPad, Android
   - Check breakpoints: 375px, 768px, 1024px, 1440px

5. **Verify SEO**:
   - Google: `site:contextfoundry.dev`
   - Check Open Graph: [Facebook Debugger](https://developers.facebook.com/tools/debug/)
   - Check Twitter Card: [Twitter Card Validator](https://cards-dev.twitter.com/validator)

---

## Continuous Deployment

### GitHub Actions (Recommended)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./
```

**Benefits**:
- Auto-deploy on push to main
- No manual deployment needed
- Version control for all changes

---

## Rollback Procedure

### GitHub Pages

1. **Revert commit**:
   ```bash
   git revert HEAD
   git push origin main
   ```

2. **Or force push previous commit**:
   ```bash
   git reset --hard HEAD~1
   git push --force origin main
   ```

### Netlify/Vercel

1. Go to Deployments
2. Find previous successful deployment
3. Click "Publish deploy"

---

## Monitoring

### Uptime Monitoring

**UptimeRobot** (Free):
- Monitor: `https://contextfoundry.dev`
- Interval: 5 minutes
- Alert: Email if site down

**Pingdom** (Free tier):
- Monitor home page load time
- Alert if > 5 seconds

### Analytics

**Plausible** (Privacy-focused):
```html
<script defer data-domain="contextfoundry.dev"
  src="https://plausible.io/js/script.js"></script>
```

**Google Analytics 4**:
```html
<script async
  src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
```

---

## Performance Optimization

### Before Production

1. **Minify CSS**:
   ```bash
   npx csso css/styles.css -o css/styles.min.css
   npx csso css/variables.css -o css/variables.min.css
   ```

2. **Minify JavaScript**:
   ```bash
   npx terser js/main.js -o js/main.min.js -c -m
   npx terser js/navigation.js -o js/navigation.min.js -c -m
   ```

3. **Update HTML references**:
   ```html
   <link rel="stylesheet" href="/css/styles.min.css">
   <script src="/js/main.min.js" defer></script>
   ```

### Server Configuration

**Enable Compression** (if using custom server):

Apache `.htaccess`:
```apache
<IfModule mod_deflate.c>
  AddOutputFilterByType DEFLATE text/html text/css application/javascript
</IfModule>
```

Nginx `nginx.conf`:
```nginx
gzip on;
gzip_types text/css application/javascript;
gzip_min_length 1000;
```

**Cache Headers**:

```apache
<FilesMatch "\.(css|js|jpg|png|svg|woff2)$">
  Header set Cache-Control "max-age=31536000, public"
</FilesMatch>
```

---

## Troubleshooting

### Site Not Loading

1. Check DNS propagation: `dig contextfoundry.dev`
2. Verify GitHub Pages enabled in settings
3. Check for build errors in Actions tab
4. Clear browser cache (Ctrl+Shift+R)

### HTTPS Not Working

1. Wait 5 minutes after DNS setup
2. Disable and re-enable "Enforce HTTPS"
3. Check CNAME file exists and is correct
4. Verify DNS points to GitHub IPs

### Custom Domain Not Working

1. Check CNAME file: `cat CNAME`
2. Verify DNS records: `dig contextfoundry.dev`
3. Wait for DNS propagation (up to 48 hours)
4. Check GitHub Pages settings

---

## Security

### Content Security Policy

Add to `index.html` `<head>`:

```html
<meta http-equiv="Content-Security-Policy"
  content="default-src 'self';
           script-src 'self';
           style-src 'self' 'unsafe-inline';
           img-src 'self' data:;">
```

### Security Headers

Configure in hosting provider or server:

```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

---

## Maintenance

### Monthly Tasks

- [ ] Review analytics (traffic, bounce rate)
- [ ] Check uptime reports
- [ ] Test all links (use broken link checker)
- [ ] Review Lighthouse scores
- [ ] Update dependencies (if any added)

### Quarterly Tasks

- [ ] Review and update content
- [ ] Check for browser compatibility issues
- [ ] Optimize images (if new ones added)
- [ ] Review and update documentation links

---

**Last Updated**: 2025-01-13
**Version**: 1.0.0
