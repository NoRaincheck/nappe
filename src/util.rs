pub fn trim_bytes(s: &[u8]) -> &[u8] {
    let start = s
        .iter()
        .position(|&b| b != b' ' && b != b'\t' && b != b'\n' && b != b'\r')
        .unwrap_or(s.len());
    let end = s
        .iter()
        .rposition(|&b| b != b' ' && b != b'\t' && b != b'\n' && b != b'\r')
        .map(|p| p + 1)
        .unwrap_or(0);
    if start >= end {
        &[]
    } else {
        &s[start..end]
    }
}

pub fn is_blank(s: &[u8]) -> bool {
    trim_bytes(s).is_empty()
}
