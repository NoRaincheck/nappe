use crate::rules::{FixSafety, Suggestion};

pub fn format_text(suggestions: &[Suggestion]) -> String {
    if suggestions.is_empty() {
        return String::new();
    }
    let mut lines = Vec::new();
    for s in suggestions {
        lines.push(format!(
            "{}:{}:{}: {} {}",
            s.file_path, s.line, s.col, s.rule.code, s.rule.description
        ));
        if !s.context.is_empty() {
            lines.push(format!("    {} | {}", s.line, s.context));
            let marker_len = format!("{}", s.line).len() + 4;
            let trimmed = s.context.trim();
            let marker = " ".repeat(marker_len) + &"^".repeat(trimmed.len());
            lines.push(format!("{} {}", marker, s.rule.code));
        }
        lines.push(String::new());
    }
    let safe = suggestions
        .iter()
        .filter(|s| s.rule.safety == FixSafety::Safe)
        .count();
    let unsafe_count = suggestions
        .iter()
        .filter(|s| s.rule.safety == FixSafety::Unsafe)
        .count();
    lines.push(format!(
        "Found {} issue{} ({} safe, {} unsafe).",
        suggestions.len(),
        if suggestions.len() != 1 { "s" } else { "" },
        safe,
        unsafe_count
    ));
    lines.join("\n")
}

pub fn format_diff(suggestions: &[Suggestion]) -> String {
    if suggestions.is_empty() {
        return String::new();
    }
    let mut lines = Vec::new();
    for s in suggestions {
        lines.push(format!("--- a/{}", s.file_path));
        lines.push(format!("+++ b/{}", s.file_path));
        lines.push(format!("@@ -{},1 +{},1 @@", s.line, s.line));
        lines.push(format!("-{}", s.context));
        let new_lines: Vec<&str> = std::str::from_utf8(&s.new_source)
            .unwrap_or("")
            .split('\n')
            .collect();
        let new_line = new_lines.first().copied().unwrap_or("");
        lines.push(format!("+{}", new_line));
        lines.push(String::new());
    }
    lines.join("\n")
}

pub fn format_json(suggestions: &[Suggestion]) -> String {
    let items: Vec<String> = suggestions
        .iter()
        .map(|s| {
            format!(
                r#"  {{ "file": "{}", "line": {}, "col": {}, "code": "{}", "message": "{}", "safety": "{}" }}"#,
                s.file_path, s.line, s.col, s.rule.code, s.rule.description, s.rule.safety.as_str()
            )
        })
        .collect();
    format!("[\n{}\n]", items.join(",\n"))
}

pub fn apply_fixes(suggestions: &[Suggestion], safety: FixSafety) -> Vec<(String, Vec<u8>)> {
    let mut by_file: Vec<(&str, &Suggestion)> = suggestions
        .iter()
        .filter(|s| s.rule.safety == safety)
        .map(|s| (s.file_path.as_str(), s))
        .collect();
    by_file.sort_by_key(|(_, s)| s.file_path.clone());
    by_file.dedup_by_key(|(_, s)| s.file_path.clone());

    let mut results = Vec::new();
    for (file_path, _) in &by_file {
        let file_suggestions: Vec<&Suggestion> = suggestions
            .iter()
            .filter(|s| s.file_path == *file_path && s.rule.safety == safety)
            .collect();
        if let Some(first) = file_suggestions.first() {
            let mut source = first.old_source.clone();
            for s in file_suggestions.iter().rev() {
                source = s.new_source.clone();
            }
            results.push((file_path.to_string(), source));
        }
    }
    results
}
