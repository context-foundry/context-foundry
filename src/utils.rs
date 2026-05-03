use std::io;
use std::path::Path;

/// Truncate a string to at most `max_bytes` bytes, ensuring the cut
/// lands on a UTF-8 character boundary. Returns a `&str` that is
/// always valid UTF-8 and at most `max_bytes` bytes long.
pub fn truncate_str(s: &str, max_bytes: usize) -> &str {
    if s.len() <= max_bytes {
        return s;
    }
    let mut end = max_bytes;
    while end > 0 && !s.is_char_boundary(end) {
        end -= 1;
    }
    &s[..end]
}

/// Truncate a string to the last `max_bytes` bytes, ensuring the slice starts
/// on a UTF-8 character boundary. Returns a `&str` that is always valid UTF-8
/// and at most `max_bytes` bytes long.
pub fn truncate_str_from_end(s: &str, max_bytes: usize) -> &str {
    if s.len() <= max_bytes {
        return s;
    }

    let mut start = s.len().saturating_sub(max_bytes);
    while start < s.len() && !s.is_char_boundary(start) {
        start += 1;
    }
    &s[start..]
}

pub fn atomic_write_file(path: &Path, contents: &[u8]) -> io::Result<()> {
    let file_name = path.file_name().and_then(|n| n.to_str()).unwrap_or("file");
    let tmp = path.with_file_name(format!(".{}.tmp", file_name));
    std::fs::write(&tmp, contents)?;
    std::fs::rename(&tmp, path).inspect_err(|_| {
        let _ = std::fs::remove_file(&tmp);
    })?;
    Ok(())
}

pub fn atomic_write_file_best_effort(path: &Path, contents: &[u8]) {
    let _ = atomic_write_file(path, contents);
}

/// Returns the user's home directory, falling back to `USERPROFILE` on Windows.
pub fn home_dir() -> Option<std::path::PathBuf> {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .ok()
        .map(std::path::PathBuf::from)
}
