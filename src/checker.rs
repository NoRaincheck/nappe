use crate::grammar::Grammar;
use crate::parser::parse_source;
use crate::rules::{Suggestion, RULES};
use crate::util::trim_bytes;

fn byte_to_line_col(source: &[u8], byte_offset: usize) -> (usize, usize) {
    let before = &source[..byte_offset];
    let line = before.iter().filter(|&&b| b == b'\n').count() + 1;
    let last_nl = before.iter().rposition(|&b| b == b'\n');
    let col = match last_nl {
        Some(pos) => byte_offset - pos - 1,
        None => byte_offset,
    };
    (line, col + 1)
}

fn get_context_line(source: &[u8], byte_offset: usize) -> String {
    let last_nl = source[..byte_offset].iter().rposition(|&b| b == b'\n');
    let next_nl = source[byte_offset..].iter().position(|&b| b == b'\n');
    let start = last_nl.map(|p| p + 1).unwrap_or(0);
    let end = byte_offset + next_nl.unwrap_or(source.len() - byte_offset);
    std::str::from_utf8(&source[start..end])
        .unwrap_or("")
        .to_string()
}

fn get_name_after_kind(
    source: &[u8],
    node_kinds: &[String],
    node_byte_starts: &[usize],
    node_byte_ends: &[usize],
    target_kind: &str,
) -> Option<String> {
    for (i, kind) in node_kinds.iter().enumerate() {
        if kind == target_kind {
            return Some(
                std::str::from_utf8(&source[node_byte_starts[i]..node_byte_ends[i]])
                    .unwrap_or("")
                    .to_string(),
            );
        }
    }
    None
}

fn count_references(source: &[u8], name: &str, after_byte: usize) -> usize {
    let text = std::str::from_utf8(source).unwrap_or("");
    let mut count = 0;
    let mut search_from = 0;
    loop {
        let idx = match text[search_from..].find(name) {
            Some(i) => i + search_from,
            None => break,
        };
        let byte_idx = text[..idx].len();
        if byte_idx >= after_byte {
            let before = text.get(idx - 1..idx).unwrap_or("");
            let after = text
                .get(idx + name.len()..idx + name.len() + 1)
                .unwrap_or("");
            let before_ok = before.is_empty() || !before.chars().next().unwrap().is_alphanumeric();
            let after_ok = after.is_empty() || !after.chars().next().unwrap().is_alphanumeric();
            if before_ok && after_ok {
                count += 1;
            }
        }
        search_from = idx + 1;
    }
    count
}

fn is_used_after(name: &str, after_byte: usize, source: &[u8]) -> bool {
    let text = std::str::from_utf8(source).unwrap_or("");
    let mut search_from = 0;
    loop {
        let idx = match text[search_from..].find(name) {
            Some(i) => i + search_from,
            None => break,
        };
        let byte_idx = text[..idx].len();
        if byte_idx >= after_byte {
            let before = text.get(idx - 1..idx).unwrap_or("");
            let after = text
                .get(idx + name.len()..idx + name.len() + 1)
                .unwrap_or("");
            let before_ok = before.is_empty() || !before.chars().next().unwrap().is_alphanumeric();
            let after_ok = after.is_empty() || !after.chars().next().unwrap().is_alphanumeric();
            if before_ok && after_ok {
                return true;
            }
        }
        search_from = idx + 1;
    }
    false
}

pub fn check_dead_functions(source: &[u8], grammar: &Grammar, file_path: &str) -> Vec<Suggestion> {
    let result = parse_source(source, grammar);
    let mut suggestions = Vec::new();
    for node in &result.all_nodes {
        if node.kind != "function_definition" {
            continue;
        }
        let name = match get_name_after_kind(
            source,
            &node.child_kinds,
            &node.child_byte_starts,
            &node.child_byte_ends,
            "identifier",
        ) {
            Some(n) => n,
            None => continue,
        };
        if name.starts_with('_') {
            continue;
        }
        let callers = count_references(source, &name, node.byte_end);
        if callers > 0 {
            continue;
        }
        let (line, col) = byte_to_line_col(source, node.byte_start);
        let mut new_source = Vec::with_capacity(source.len());
        new_source.extend_from_slice(&source[..node.byte_start]);
        new_source.extend_from_slice(&source[node.byte_end..]);
        let trimmed = trim_bytes(&new_source);
        let mut final_source = trimmed.to_vec();
        final_source.push(b'\n');
        let ctx = get_context_line(source, node.byte_start);
        suggestions.push(Suggestion {
            file_path: file_path.to_string(),
            line,
            col,
            rule: &RULES["RED100"],
            old_source: source.to_vec(),
            new_source: final_source,
            context: ctx,
        });
    }
    suggestions
}

pub fn check_dead_classes(source: &[u8], grammar: &Grammar, file_path: &str) -> Vec<Suggestion> {
    let result = parse_source(source, grammar);
    let mut suggestions = Vec::new();
    for node in &result.all_nodes {
        if node.kind != "class_definition" {
            continue;
        }
        let name = match get_name_after_kind(
            source,
            &node.child_kinds,
            &node.child_byte_starts,
            &node.child_byte_ends,
            "identifier",
        ) {
            Some(n) => n,
            None => continue,
        };
        if name.starts_with('_') {
            continue;
        }
        let refs = count_references(source, &name, node.byte_end);
        if refs > 0 {
            continue;
        }
        let (line, col) = byte_to_line_col(source, node.byte_start);
        let mut new_source = Vec::with_capacity(source.len());
        new_source.extend_from_slice(&source[..node.byte_start]);
        new_source.extend_from_slice(&source[node.byte_end..]);
        let trimmed = trim_bytes(&new_source);
        let mut final_source = trimmed.to_vec();
        final_source.push(b'\n');
        let ctx = get_context_line(source, node.byte_start);
        suggestions.push(Suggestion {
            file_path: file_path.to_string(),
            line,
            col,
            rule: &RULES["RED101"],
            old_source: source.to_vec(),
            new_source: final_source,
            context: ctx,
        });
    }
    suggestions
}

pub fn check_unused_assignments(
    source: &[u8],
    grammar: &Grammar,
    file_path: &str,
) -> Vec<Suggestion> {
    let result = parse_source(source, grammar);
    let mut suggestions = Vec::new();
    for node in &result.all_nodes {
        if node.kind != "assignment" && node.kind != "augmented_assignment" {
            continue;
        }
        let var_name = match get_name_after_kind(
            source,
            &node.child_kinds,
            &node.child_byte_starts,
            &node.child_byte_ends,
            "identifier",
        ) {
            Some(n) => n,
            None => continue,
        };
        if var_name.starts_with('_') {
            continue;
        }
        if is_used_after(&var_name, node.byte_end, source) {
            continue;
        }
        let (line, col) = byte_to_line_col(source, node.byte_start);
        let mut new_source = Vec::with_capacity(source.len());
        new_source.extend_from_slice(&source[..node.byte_start]);
        new_source.extend_from_slice(&source[node.byte_end..]);
        let trimmed = trim_bytes(&new_source);
        let mut final_source = trimmed.to_vec();
        final_source.push(b'\n');
        let ctx = get_context_line(source, node.byte_start);
        suggestions.push(Suggestion {
            file_path: file_path.to_string(),
            line,
            col,
            rule: &RULES["RED102"],
            old_source: source.to_vec(),
            new_source: final_source,
            context: ctx,
        });
    }
    suggestions
}

pub fn check_constant_expressions(
    source: &[u8],
    grammar: &Grammar,
    file_path: &str,
) -> Vec<Suggestion> {
    let result = parse_source(source, grammar);
    let mut suggestions = Vec::new();
    for node in &result.all_nodes {
        if node.kind != "binary_operator"
            && node.kind != "boolean_operator"
            && node.kind != "comparison_operator"
        {
            continue;
        }
        let text = std::str::from_utf8(&source[node.byte_start..node.byte_end]).unwrap_or("");
        let evaled = safe_eval(text.trim());
        let evaled = match evaled {
            Some(v) => v,
            None => continue,
        };
        let replacement = evaled.into_bytes();
        if replacement == source[node.byte_start..node.byte_end] {
            continue;
        }
        let (line, col) = byte_to_line_col(source, node.byte_start);
        let mut new_source = Vec::with_capacity(source.len());
        new_source.extend_from_slice(&source[..node.byte_start]);
        new_source.extend_from_slice(&replacement);
        new_source.extend_from_slice(&source[node.byte_end..]);
        let ctx = get_context_line(source, node.byte_start);
        suggestions.push(Suggestion {
            file_path: file_path.to_string(),
            line,
            col,
            rule: &RULES["RED200"],
            old_source: source.to_vec(),
            new_source,
            context: ctx,
        });
    }
    suggestions
}

fn safe_eval(s: &str) -> Option<String> {
    // Simple integer/boolean evaluator
    if let Some(v) = eval_int_simple(s) {
        return Some(v.to_string());
    }
    // Boolean comparisons
    for op in &["==", "!=", "<=", ">=", "<", ">"] {
        if let Some((left, right)) = s.split_once(op) {
            let l = parse_int(left.trim())?;
            let r = parse_int(right.trim())?;
            let result = match *op {
                "==" => l == r,
                "!=" => l != r,
                "<=" => l <= r,
                ">=" => l >= r,
                "<" => l < r,
                ">" => l > r,
                _ => unreachable!(),
            };
            return Some(if result {
                "True".to_string()
            } else {
                "False".to_string()
            });
        }
    }
    // Boolean and/or
    if let Some((left, right)) = s.split_once(" and ") {
        let l = safe_eval(left.trim())?;
        let r = safe_eval(right.trim())?;
        return Some(if l == "True" && r == "True" {
            "True".to_string()
        } else {
            "False".to_string()
        });
    }
    if let Some((left, right)) = s.split_once(" or ") {
        let l = safe_eval(left.trim())?;
        let r = safe_eval(right.trim())?;
        return Some(if l == "True" || r == "True" {
            "True".to_string()
        } else {
            "False".to_string()
        });
    }
    None
}

fn eval_int_simple(s: &str) -> Option<i64> {
    let s = s.trim();
    if let Ok(v) = s.parse::<i64>() {
        return Some(v);
    }
    // Simple binary ops
    for op in &["+", "-", "*", "/", "%"] {
        if let Some(pos) = find_operator(s, op) {
            let left = s[..pos].trim();
            let right = s[pos + op.len()..].trim();
            if let (Some(l), Some(r)) = (parse_int(left), parse_int(right)) {
                return match *op {
                    "+" => Some(l + r),
                    "-" => Some(l - r),
                    "*" => Some(l * r),
                    "/" => {
                        if r == 0 {
                            None
                        } else {
                            Some(l / r)
                        }
                    }
                    "%" => {
                        if r == 0 {
                            None
                        } else {
                            Some(l % r)
                        }
                    }
                    _ => None,
                };
            }
        }
    }
    None
}

fn find_operator(s: &str, op: &str) -> Option<usize> {
    let mut depth = 0;
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        match chars[i] {
            '(' => depth += 1,
            ')' => depth -= 1,
            _ if depth == 0 => {
                if i > 0 && s[i..].starts_with(op) {
                    // Make sure it's not part of a longer operator
                    let prev = chars[i - 1];
                    if prev == '('
                        || prev == ' '
                        || prev == '+'
                        || prev == '-'
                        || prev == '*'
                        || prev == '/'
                        || prev == '%'
                    {
                        // Check next char isn't same (for **, //)
                        if i + op.len() < chars.len() {
                            let next = chars[i + op.len()];
                            if next == chars[i] {
                                i += 1;
                                continue;
                            }
                        }
                        return Some(i);
                    }
                }
            }
            _ => {}
        }
        i += 1;
    }
    None
}

fn parse_int(s: &str) -> Option<i64> {
    let s = s.trim();
    if let Ok(v) = s.parse::<i64>() {
        return Some(v);
    }
    if s == "True" || s == "true" {
        return Some(1);
    }
    if s == "False" || s == "false" {
        return Some(0);
    }
    None
}

pub fn check_redundant_parens(
    source: &[u8],
    grammar: &Grammar,
    file_path: &str,
) -> Vec<Suggestion> {
    let result = parse_source(source, grammar);
    let mut suggestions = Vec::new();
    for node in &result.all_nodes {
        if node.kind != "parenthesized_expression" {
            continue;
        }
        if node.child_kinds.len() != 3 {
            continue;
        }
        if node.child_kinds[0] != "(" || node.child_kinds[2] != ")" {
            continue;
        }
        let inner_start = node.child_byte_starts[1];
        let inner_end = node.child_byte_ends[1];
        let inner = &source[inner_start..inner_end];
        let text = &source[node.byte_start..node.byte_end];
        if text == inner {
            continue;
        }
        let (line, col) = byte_to_line_col(source, node.byte_start);
        let mut new_source = Vec::with_capacity(source.len());
        new_source.extend_from_slice(&source[..node.byte_start]);
        new_source.extend_from_slice(inner);
        new_source.extend_from_slice(&source[node.byte_end..]);
        let ctx = get_context_line(source, node.byte_start);
        suggestions.push(Suggestion {
            file_path: file_path.to_string(),
            line,
            col,
            rule: &RULES["RED201"],
            old_source: source.to_vec(),
            new_source,
            context: ctx,
        });
    }
    suggestions
}

pub fn check_unnecessary_semicolons(
    source: &[u8],
    _grammar: &Grammar,
    file_path: &str,
) -> Vec<Suggestion> {
    let mut suggestions = Vec::new();
    let lines: Vec<&[u8]> = source.split(|&b| b == b'\n').collect();
    let mut offset = 0;
    for (i, line_bytes) in lines.iter().enumerate() {
        let stripped = line_bytes.iter().rposition(|&b| b != b' ' && b != b'\t');
        if let Some(pos) = stripped {
            if line_bytes[pos] == b';' {
                let new_line = &line_bytes[..pos];
                let new_source = [
                    &source[..offset],
                    new_line,
                    b"\n",
                    &source[offset + line_bytes.len() + 1..],
                ]
                .concat();
                let line_num = i + 1;
                let col = line_bytes.len() - 1;
                let ctx = std::str::from_utf8(line_bytes).unwrap_or("").to_string();
                suggestions.push(Suggestion {
                    file_path: file_path.to_string(),
                    line: line_num,
                    col,
                    rule: &RULES["RED202"],
                    old_source: source.to_vec(),
                    new_source,
                    context: ctx,
                });
            }
        }
        offset += line_bytes.len() + 1;
    }
    suggestions
}

pub fn check_trailing_whitespace(
    source: &[u8],
    _grammar: &Grammar,
    file_path: &str,
) -> Vec<Suggestion> {
    let mut suggestions = Vec::new();
    let lines: Vec<&[u8]> = source.split(|&b| b == b'\n').collect();
    let mut offset = 0;
    for (i, line_bytes) in lines.iter().enumerate() {
        if *line_bytes
            != line_bytes
                .iter()
                .rposition(|&b| b != b' ' && b != b'\t')
                .map(|p| &line_bytes[..=p])
                .unwrap_or(b"")
        {
            let new_line = line_bytes
                .iter()
                .rposition(|&b| b != b' ' && b != b'\t')
                .map(|p| &line_bytes[..=p])
                .unwrap_or(b"");
            let new_source = [
                &source[..offset],
                new_line,
                &source[offset + line_bytes.len()..],
            ]
            .concat();
            let line_num = i + 1;
            let col = new_line.len();
            let ctx = std::str::from_utf8(line_bytes).unwrap_or("").to_string();
            suggestions.push(Suggestion {
                file_path: file_path.to_string(),
                line: line_num,
                col,
                rule: &RULES["RED203"],
                old_source: source.to_vec(),
                new_source,
                context: ctx,
            });
        }
        offset += line_bytes.len() + 1;
    }
    suggestions
}

pub fn check_redundant_newlines(
    source: &[u8],
    _grammar: &Grammar,
    file_path: &str,
) -> Vec<Suggestion> {
    let mut suggestions = Vec::new();
    if source.ends_with(b"\n\n") {
        let stripped = source
            .iter()
            .rposition(|&b| b != b'\n')
            .map(|pos| {
                let mut result = source[..=pos].to_vec();
                result.push(b'\n');
                result
            })
            .unwrap_or_default();
        if stripped != source {
            let line_num = source.iter().filter(|&&b| b == b'\n').count() + 1;
            suggestions.push(Suggestion {
                file_path: file_path.to_string(),
                line: line_num,
                col: 0,
                rule: &RULES["RED204"],
                old_source: source.to_vec(),
                new_source: stripped,
                context: String::new(),
            });
        }
    }
    suggestions
}

pub fn all_checks() -> Vec<fn(&[u8], &Grammar, &str) -> Vec<Suggestion>> {
    vec![
        check_trailing_whitespace,
        check_redundant_newlines,
        check_unnecessary_semicolons,
        check_redundant_parens,
        check_constant_expressions,
        check_unused_assignments,
        check_dead_functions,
        check_dead_classes,
    ]
}
