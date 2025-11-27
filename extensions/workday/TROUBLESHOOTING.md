# WorkWise Troubleshooting Guide

Quick reference for common issues encountered during the WorkWise build.

---

## 🔥 Common Build Errors

### Error: "Cannot find module 'package-name'"

**Symptom**: Module not found despite being in package.json

**Quick Fix**:
```bash
npm install <package-name>
```

**Comprehensive Fix**:
```bash
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

**Verify**:
```bash
npm list --depth=0 | grep UNMET
```

---

### Error: "Expected '>', got 'value'"

**Symptom**: SWC parser error on JSX syntax

**Cause**: JSX in a `.ts` file instead of `.tsx`

**Fix**:
```bash
# Find the problematic file
find . -name "*.ts" -not -name "*.d.ts" -exec grep -l "</" {} \;

# Rename it
mv path/to/file.ts path/to/file.tsx

# Clear cache
rm -rf .next

# Restart
npm run dev
```

---

### Error: "Failed to read source code from .../filename.ts"

**Symptom**: File exists but Next.js can't find it

**Cause**: Stale webpack cache after file rename

**Fix**:
```bash
rm -rf .next node_modules/.cache
npm run dev
```

---

### Build Timeout After 30 Minutes

**Symptom**: Builder phase times out, retries automatically

**Cause**: Too much AI content generation at build time

**Fix**: Let the daemon retry (it will complete incrementally)

**Better Solution**: Use on-demand generation instead of build-time

---

## 🛠️ Useful Commands

### Clean Everything
```bash
rm -rf .next node_modules package-lock.json
npm cache clean --force
npm install
```

### Verify Installation
```bash
npm list --depth=0
npm run dev
```

### Find JSX in .ts Files
```bash
find . -name "*.ts" -not -name "*.d.ts" -exec grep -l "</" {} \;
```

### Check for UNMET Dependencies
```bash
npm list --depth=0 | grep UNMET
```

---

## 📋 Pre-Flight Checklist

Before starting development:

- [ ] Run `npm install`
- [ ] Check for UNMET deps: `npm list --depth=0`
- [ ] Verify .env.local exists with OPENAI_API_KEY
- [ ] Check all .tsx files for JSX (not .ts)
- [ ] Clear caches: `rm -rf .next`
- [ ] Test: `npm run dev`

---

## 🔍 Debugging Steps

1. **Check npm install success**:
   ```bash
   ls node_modules/ | wc -l  # Should be ~800+
   ```

2. **Check for JSX in wrong files**:
   ```bash
   find . -name "*.ts" -not -name "*.d.ts" -exec grep -l "<[A-Z]" {} \;
   ```

3. **Clear all caches**:
   ```bash
   rm -rf .next node_modules/.cache
   ```

4. **Verify TypeScript config**:
   ```bash
   cat tsconfig.json | grep -A5 "compilerOptions"
   ```

5. **Check dev server logs**:
   ```bash
   npm run dev 2>&1 | tee build.log
   ```

---

## 📖 Common Questions

### Q: Why does npm install fail?
**A**: Usually network or cache issues. Try:
```bash
npm cache clean --force
npm install
```

### Q: Why can't Next.js find my renamed file?
**A**: Cache is stale. Clear it:
```bash
rm -rf .next
```

### Q: Should I use .ts or .tsx?
**A**:
- Use `.ts` for pure TypeScript (no JSX)
- Use `.tsx` for React components (with JSX)

### Q: How do I know if the build succeeded?
**A**: Check for:
- No errors in console
- HTTP 200 on http://localhost:3000
- Page displays "WorkWise - Workday Expertise Platform"

---

## 🎯 Quick Recovery

If everything is broken:

```bash
# Nuclear option - reset everything
rm -rf .next node_modules package-lock.json
npm cache clean --force
npm install
npm run dev
```

Then visit http://localhost:3000

---

## 📞 Getting Help

If stuck:
1. Check this guide first
2. Review `BUILD_FAILURE_PATTERNS.md`
3. Check daemon logs: `cfd logs <job-id>`
4. Review `.context-foundry/current-phase.json`

---

## ✅ Success Indicators

Build is successful when:
- ✅ `npm run dev` starts without errors
- ✅ Port 3000 responds with HTTP 200
- ✅ Page title shows "WorkWise - Workday Expertise Platform"
- ✅ No console errors in browser
- ✅ Navigation works (Home, Patterns, Progress)

---

**Last Updated**: 2025-11-23
**Version**: 1.0.0
