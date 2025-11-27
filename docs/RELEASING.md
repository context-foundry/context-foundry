# Releasing Context Foundry

This document describes how to create new releases of Context Foundry.

## Version Management

**Single Source of Truth:** `__version__.py` is the master version file. All other files derive from it.

### Files that contain version numbers:
| File | Purpose | How it's updated |
|------|---------|------------------|
| `__version__.py` | Master version | Manual or via script |
| `setup.py` | Python package | Reads from `__version__.py` |
| `npm/package.json` | npm package | Synced by script/CI |
| `public/index.html` | Website cache-busting | Synced by script/CI |

## Release Process

### Option 1: Automated Release (Recommended)

Simply tag and push - GitHub Actions handles everything:

```bash
# Bump version locally first
./scripts/sync-version.sh 2.6.0

# Commit and tag
git add -A
git commit -m "chore: bump version to 2.6.0"
git tag v2.6.0

# Push (triggers automated release)
git push origin main --tags
```

GitHub Actions will:
1. Sync version to all files
2. Build Python package
3. Publish to PyPI
4. Publish to npm
5. Create GitHub Release with release notes
6. Commit version sync back to main

### Option 2: Manual Release

For more control over the release process:

```bash
# 1. Sync versions
./scripts/sync-version.sh 2.6.0

# 2. Build Python package
python -m build

# 3. Upload to PyPI
twine upload dist/*

# 4. Publish npm package
cd npm && npm publish --access public && cd ..

# 5. Create GitHub release
gh release create v2.6.0 dist/* --generate-notes
```

## Pre-release Checklist

- [ ] All tests passing (`pytest tests/`)
- [ ] CI pipeline green
- [ ] CHANGELOG.md updated
- [ ] Version number follows semantic versioning

## Versioning Guidelines

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (x.0.0): Breaking changes
- **MINOR** (0.x.0): New features, backwards compatible
- **PATCH** (0.0.x): Bug fixes, backwards compatible

## Secrets Required

The following secrets must be configured in GitHub repository settings:

| Secret | Purpose |
|--------|---------|
| `PYPI_TOKEN` | PyPI API token for publishing |
| `NPM_TOKEN` | npm access token for publishing |

## Website Version

The website at `public/index.html` displays the version in two ways:

1. **Static fallback**: Hardcoded in footer (synced by release script)
2. **Dynamic fetch**: JavaScript fetches latest from npm registry

This ensures the website always shows the current version even if the static version is outdated.

## Troubleshooting

### PyPI upload fails
- Check `PYPI_TOKEN` secret is valid
- Ensure version doesn't already exist on PyPI

### npm publish fails
- Check `NPM_TOKEN` secret is valid
- Ensure version doesn't already exist on npm
- Verify `npm/package.json` has correct name

### Version mismatch
Run the sync script to align all files:
```bash
./scripts/sync-version.sh
```
