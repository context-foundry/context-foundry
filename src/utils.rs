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
