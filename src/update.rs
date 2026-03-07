use anyhow::{bail, Context, Result};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, SystemTime};

const GITHUB_REPO: &str = "context-foundry/context-foundry";
const GITHUB_API_RELEASES: &str =
    "https://api.github.com/repos/context-foundry/context-foundry/releases";
const CHECK_INTERVAL: Duration = Duration::from_secs(24 * 60 * 60); // 24 hours
const ASSET_PREFIX: &str = "foundry-v";

// ─── Version helpers ─────────────────────────────────────────

pub fn current_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

fn parse_version(s: &str) -> Vec<u32> {
    s.trim_start_matches('v')
        .split('.')
        .filter_map(|p| p.parse::<u32>().ok())
        .collect()
}

fn is_newer(remote: &str, local: &str) -> bool {
    let r = parse_version(remote);
    let l = parse_version(local);
    r > l
}

// ─── Target triple ───────────────────────────────────────────

pub fn get_target_triple() -> Option<&'static str> {
    match (std::env::consts::OS, std::env::consts::ARCH) {
        ("macos", "aarch64") => Some("aarch64-apple-darwin"),
        ("macos", "x86_64") => Some("x86_64-apple-darwin"),
        ("linux", "x86_64") => Some("x86_64-unknown-linux-gnu"),
        ("linux", "aarch64") => Some("aarch64-unknown-linux-gnu"),
        _ => None,
    }
}

// ─── Cache dir ───────────────────────────────────────────────

fn foundry_cache_dir() -> Result<PathBuf> {
    let home = std::env::var("HOME").context("HOME not set")?;
    let dir = PathBuf::from(home).join(".foundry");
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

// ─── Rate-limited update check ───────────────────────────────

pub fn check_for_update() -> Result<Option<String>> {
    let cache_dir = foundry_cache_dir()?;
    let check_file = cache_dir.join("last-update-check");

    // Rate limit: skip if checked within 24h
    if let Ok(meta) = fs::metadata(&check_file) {
        if let Ok(modified) = meta.modified() {
            if SystemTime::now()
                .duration_since(modified)
                .unwrap_or(Duration::MAX)
                < CHECK_INTERVAL
            {
                // Read cached result
                if let Ok(cached) = fs::read_to_string(&check_file) {
                    let cached = cached.trim().to_string();
                    if !cached.is_empty() && is_newer(&cached, current_version()) {
                        return Ok(Some(cached));
                    }
                }
                return Ok(None);
            }
        }
    }

    // Fetch latest binary release (skips Python-only releases)
    let latest = match fetch_latest_binary_release() {
        Ok(Some(rel)) => rel.version,
        Ok(None) => {
            // No binary releases found — cache empty result
            let _ = fs::write(&check_file, "");
            return Ok(None);
        }
        Err(_) => {
            // Network failure — don't block, just skip
            return Ok(None);
        }
    };

    // Cache the result (write the version tag)
    let _ = fs::write(&check_file, &latest);

    if is_newer(&latest, current_version()) {
        Ok(Some(latest))
    } else {
        Ok(None)
    }
}

// ─── Fetch latest Rust binary release from GitHub API ────────

/// A release that contains foundry binary assets.
struct BinaryRelease {
    version: String,
    body: String, // raw JSON for asset extraction
}

/// Fetches recent releases and returns the first one that contains
/// foundry binary assets (i.e. files matching `foundry-v*-*.tar.gz`).
/// This skips Python-only releases like the context_foundry wheel packages.
fn fetch_latest_binary_release() -> Result<Option<BinaryRelease>> {
    let output = Command::new("curl")
        .args([
            "-sfL",
            "--max-time",
            "10",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "User-Agent: foundry-updater",
            // Fetch up to 20 recent releases to scan past Python-only ones
            &format!("{}?per_page=20", GITHUB_API_RELEASES),
        ])
        .output()
        .context("failed to run curl")?;

    if !output.status.success() {
        bail!("GitHub API request failed");
    }

    let body = String::from_utf8_lossy(&output.stdout);
    let releases: Vec<serde_json::Value> =
        serde_json::from_str(&body).context("failed to parse GitHub API response")?;

    for release in &releases {
        // Skip drafts and pre-releases
        if release
            .get("draft")
            .and_then(|d| d.as_bool())
            .unwrap_or(false)
        {
            continue;
        }
        if release
            .get("prerelease")
            .and_then(|p| p.as_bool())
            .unwrap_or(false)
        {
            continue;
        }

        let assets = match release.get("assets").and_then(|a| a.as_array()) {
            Some(a) => a,
            None => continue,
        };

        // Check if any asset looks like a foundry binary tarball
        let has_binary = assets.iter().any(|asset| {
            asset
                .get("name")
                .and_then(|n| n.as_str())
                .map(|name| name.starts_with(ASSET_PREFIX) && name.ends_with(".tar.gz"))
                .unwrap_or(false)
        });

        if has_binary {
            let tag = release
                .get("tag_name")
                .and_then(|t| t.as_str())
                .context("no tag_name in release")?;
            let version = tag.trim_start_matches('v').to_string();
            let release_json = serde_json::to_string(release)?;
            return Ok(Some(BinaryRelease {
                version,
                body: release_json,
            }));
        }
    }

    Ok(None)
}

fn extract_assets(json: &str) -> Result<Vec<(String, String)>> {
    let v: serde_json::Value = serde_json::from_str(json)?;
    let assets = v
        .get("assets")
        .and_then(|a| a.as_array())
        .context("no assets in release")?;

    let mut result = Vec::new();
    for asset in assets {
        let name = asset.get("name").and_then(|n| n.as_str()).unwrap_or("");
        let url = asset
            .get("browser_download_url")
            .and_then(|u| u.as_str())
            .unwrap_or("");
        if !name.is_empty() && !url.is_empty() {
            result.push((name.to_string(), url.to_string()));
        }
    }
    Ok(result)
}

// ─── Self-update flow ────────────────────────────────────────

pub fn run_update() -> Result<()> {
    let current = current_version();
    println!("Foundry v{}", current);

    // Detect Homebrew install
    let self_path = std::env::current_exe().context("cannot determine executable path")?;
    let self_path_str = self_path.to_string_lossy();
    if self_path_str.contains("homebrew") || self_path_str.contains("Cellar") {
        println!("Installed via Homebrew. Use:");
        println!("  brew upgrade context-foundry/tap/foundry");
        return Ok(());
    }

    println!("Checking for updates...");

    let release = match fetch_latest_binary_release() {
        Ok(Some(rel)) => rel,
        Ok(None) => {
            println!("No binary releases found (only Python packages exist).");
            println!("Install from source:");
            println!(
                "  cargo install --git https://github.com/{} foundry",
                GITHUB_REPO
            );
            return Ok(());
        }
        Err(e) => {
            println!("Failed to check for updates: {}", e);
            println!("Install from source:");
            println!(
                "  cargo install --git https://github.com/{} foundry",
                GITHUB_REPO
            );
            return Ok(());
        }
    };

    let latest = &release.version;

    if !is_newer(latest, current) {
        println!("Already at latest version (v{}).", current);
        if let Ok(dir) = foundry_cache_dir() {
            let _ = fs::write(dir.join("last-update-check"), latest);
        }
        return Ok(());
    }

    println!("New version available: v{} → v{}", current, latest);

    let target = match get_target_triple() {
        Some(t) => t,
        None => {
            println!(
                "No prebuilt binary for this platform ({}/{}).",
                std::env::consts::OS,
                std::env::consts::ARCH
            );
            println!("Install from source:");
            println!(
                "  cargo install --git https://github.com/{} foundry",
                GITHUB_REPO
            );
            return Ok(());
        }
    };

    let assets = extract_assets(&release.body)?;
    let tarball_name = format!("foundry-v{}-{}.tar.gz", latest, target);
    let checksums_name = format!("foundry-v{}-checksums.txt", latest);

    let tarball_url = assets
        .iter()
        .find(|(name, _)| name == &tarball_name)
        .map(|(_, url)| url.clone());

    let checksums_url = assets
        .iter()
        .find(|(name, _)| name == &checksums_name)
        .map(|(_, url)| url.clone());

    let tarball_url = match tarball_url {
        Some(url) => url,
        None => {
            println!(
                "No binary found for target {} in release v{}.",
                target, latest
            );
            println!("Available assets:");
            for (name, _) in &assets {
                println!("  - {}", name);
            }
            println!("\nInstall from source:");
            println!(
                "  cargo install --git https://github.com/{} foundry",
                GITHUB_REPO
            );
            return Ok(());
        }
    };

    // Create temp dir
    let tmp_dir = std::env::temp_dir().join(format!("foundry-update-{}", latest));
    let _ = fs::remove_dir_all(&tmp_dir);
    fs::create_dir_all(&tmp_dir)?;

    // Download tarball
    println!("Downloading {}...", tarball_name);
    let tarball_path = tmp_dir.join(&tarball_name);
    download_file(&tarball_url, &tarball_path)?;

    // Verify checksum if available
    if let Some(checksums_url) = checksums_url {
        println!("Verifying checksum...");
        let checksums_path = tmp_dir.join(&checksums_name);
        download_file(&checksums_url, &checksums_path)?;
        verify_checksum(&tarball_path, &tarball_name, &checksums_path)?;
        println!("Checksum verified.");
    }

    // Extract
    println!("Extracting...");
    let status = Command::new("tar")
        .args(["-xzf", &tarball_path.to_string_lossy()])
        .current_dir(&tmp_dir)
        .status()
        .context("failed to extract tarball")?;
    if !status.success() {
        bail!("tar extraction failed");
    }

    let new_binary = tmp_dir.join("foundry");
    if !new_binary.exists() {
        bail!("extracted archive does not contain 'foundry' binary");
    }

    // Replace using backup + rollback strategy
    println!("Installing...");
    replace_binary(&self_path, &new_binary)?;

    // macOS: clear quarantine
    if std::env::consts::OS == "macos" {
        let _ = Command::new("xattr")
            .args(["-cr", &self_path.to_string_lossy()])
            .status();
    }

    // Cleanup
    let _ = fs::remove_dir_all(&tmp_dir);

    // Update cache
    if let Ok(dir) = foundry_cache_dir() {
        let _ = fs::write(dir.join("last-update-check"), latest);
    }

    println!("Updated to v{}!", latest);
    Ok(())
}

// ─── Helpers ─────────────────────────────────────────────────

fn download_file(url: &str, dest: &Path) -> Result<()> {
    let status = Command::new("curl")
        .args([
            "-fSL",
            "--max-time",
            "120",
            "-o",
            &dest.to_string_lossy(),
            url,
        ])
        .status()
        .context("failed to run curl")?;
    if !status.success() {
        bail!("download failed: {}", url);
    }
    Ok(())
}

fn verify_checksum(file: &Path, file_name: &str, checksums_path: &Path) -> Result<()> {
    let checksums = fs::read_to_string(checksums_path)?;

    let expected = checksums
        .lines()
        .find(|line| line.contains(file_name))
        .and_then(|line| line.split_whitespace().next())
        .context("checksum not found for this binary")?;

    // Compute SHA256
    let output = Command::new("shasum")
        .args(["-a", "256", &file.to_string_lossy()])
        .output()
        .context("failed to run shasum")?;

    let actual = String::from_utf8_lossy(&output.stdout);
    let actual = actual.split_whitespace().next().unwrap_or("");

    if actual != expected {
        bail!(
            "checksum mismatch!\n  expected: {}\n  actual:   {}",
            expected,
            actual
        );
    }
    Ok(())
}

/// Replace the current binary with a new one.
/// Strategy: backup current → copy new → remove backup (rollback on failure).
fn replace_binary(target: &Path, source: &Path) -> Result<()> {
    let backup = target.with_extension("old");

    // Remove stale backup
    let _ = fs::remove_file(&backup);

    // Rename current → .old
    if target.exists() {
        fs::rename(target, &backup).context("failed to backup current binary")?;
    }

    // Copy new binary into place
    match fs::copy(source, target) {
        Ok(_) => {
            // Set executable permissions
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let _ = fs::set_permissions(target, fs::Permissions::from_mode(0o755));
            }
            // Remove backup
            let _ = fs::remove_file(&backup);
            Ok(())
        }
        Err(e) => {
            // Rollback: restore backup
            if backup.exists() {
                let _ = fs::rename(&backup, target);
            }
            Err(e).context("failed to install new binary (rolled back)")
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_version() {
        assert_eq!(parse_version("1.2.3"), vec![1, 2, 3]);
        assert_eq!(parse_version("v0.2.0"), vec![0, 2, 0]);
    }

    #[test]
    fn test_is_newer() {
        assert!(is_newer("0.2.0", "0.1.0"));
        assert!(is_newer("1.0.0", "0.9.9"));
        assert!(!is_newer("0.1.0", "0.2.0"));
        assert!(!is_newer("0.2.0", "0.2.0"));
    }

    #[test]
    fn test_get_target_triple() {
        let triple = get_target_triple();
        assert!(triple.is_some() || cfg!(not(any(target_os = "macos", target_os = "linux"))));
    }

    #[test]
    fn test_extract_assets_filters_binary_releases() {
        let json = r#"{
            "tag_name": "v0.3.0",
            "assets": [
                {"name": "foundry-v0.3.0-aarch64-apple-darwin.tar.gz", "browser_download_url": "https://example.com/a"},
                {"name": "context_foundry-0.3.0.tar.gz", "browser_download_url": "https://example.com/b"}
            ]
        }"#;
        let assets = extract_assets(json).unwrap();
        assert_eq!(assets.len(), 2);
        // The binary asset starts with ASSET_PREFIX
        assert!(assets[0].0.starts_with(ASSET_PREFIX));
        // The Python asset does not
        assert!(!assets[1].0.starts_with(ASSET_PREFIX));
    }
}
