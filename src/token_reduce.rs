use crate::grammar::Grammar;
use crate::parser::parse_source;
use crate::util::is_blank;

fn strip_trailing_whitespace(source: &[u8]) -> Option<Vec<u8>> {
    let lines: Vec<&[u8]> = source.split(|&b| b == b'\n').collect();
    let new_lines: Vec<Vec<u8>> = lines
        .iter()
        .map(|line| {
            let trimmed = line.iter().rposition(|&b| b != b' ' && b != b'\t');
            match trimmed {
                Some(pos) => line[..=pos].to_vec(),
                None => Vec::new(),
            }
        })
        .collect();
    let new_source = new_lines.join(&b'\n');
    if new_source == source {
        None
    } else {
        Some(new_source)
    }
}

fn strip_trailing_newlines(source: &[u8]) -> Option<Vec<u8>> {
    if !source.ends_with(b"\n") {
        return None;
    }
    let stripped = source.iter().rposition(|&b| b != b'\n').map(|pos| {
        let mut result = source[..=pos].to_vec();
        result.push(b'\n');
        result
    });
    match stripped {
        Some(s) if s == source => None,
        Some(s) => Some(s),
        None => None,
    }
}

fn remove_unnecessary_semicolons(source: &[u8], grammar: &Grammar) -> Option<(Vec<u8>, Vec<u8>)> {
    let result = parse_source(source, grammar);
    let mut changed = false;
    let mut new_source = source.to_vec();

    for node in result.all_nodes.iter().rev() {
        if node.kind == ";" && !node.has_errors {
            let mut candidate = new_source.clone();
            candidate.drain(node.byte_start..node.byte_end);
            if !is_blank(&candidate) {
                let reparse = parse_source(&candidate, grammar);
                if reparse.error_node_count == 0 {
                    new_source = candidate;
                    changed = true;
                }
            }
        }
    }

    if !changed {
        None
    } else {
        Some((source.to_vec(), new_source))
    }
}

fn remove_redundant_parens(source: &[u8], grammar: &Grammar) -> Option<Vec<u8>> {
    let result = parse_source(source, grammar);
    let mut source = source.to_vec();

    for node in result.all_nodes.iter().rev() {
        if node.kind != "parenthesized_expression" {
            continue;
        }
        if node.has_errors {
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
        let mut candidate = Vec::with_capacity(source.len());
        candidate.extend_from_slice(&source[..node.byte_start]);
        candidate.extend_from_slice(&source[inner_start..inner_end]);
        candidate.extend_from_slice(&source[node.byte_end..]);
        if !is_blank(&candidate) {
            let reparse = parse_source(&candidate, grammar);
            if reparse.error_node_count <= result.error_node_count {
                source = candidate;
            }
        }
    }
    Some(source)
}

pub fn token_reduce(
    source: &[u8],
    grammar: &Grammar,
    is_interesting: &dyn Fn(&[u8]) -> bool,
) -> Vec<u8> {
    let mut current = source.to_vec();

    // Strip trailing whitespace
    if let Some(step) = strip_trailing_whitespace(&current) {
        let reparsed = parse_source(&step, grammar);
        if reparsed.error_node_count == 0 && is_interesting(&step) {
            current = step;
        }
    }

    // Strip trailing newlines
    if let Some(step) = strip_trailing_newlines(&current) {
        let reparsed = parse_source(&step, grammar);
        if reparsed.error_node_count == 0 && is_interesting(&step) {
            current = step;
        }
    }

    // Remove redundant parens
    if let Some(step) = remove_redundant_parens(&current, grammar) {
        if step != current {
            let reparsed = parse_source(&step, grammar);
            if reparsed.error_node_count == 0 && is_interesting(&step) {
                current = step;
            }
        }
    }

    // Remove unnecessary semicolons
    if let Some((_, new_source)) = remove_unnecessary_semicolons(&current, grammar) {
        if new_source != current {
            let reparsed = parse_source(&new_source, grammar);
            if reparsed.error_node_count == 0 && is_interesting(&new_source) {
                current = new_source;
            }
        }
    }

    // Repeat whitespace/newline stripping up to 3 times
    for _ in 0..3 {
        let prev = current.clone();

        if let Some(step) = strip_trailing_whitespace(&current) {
            let reparsed = parse_source(&step, grammar);
            if reparsed.error_node_count == 0 && is_interesting(&step) {
                current = step;
            }
        }

        if let Some(step) = strip_trailing_newlines(&current) {
            let reparsed = parse_source(&step, grammar);
            if reparsed.error_node_count == 0 && is_interesting(&step) {
                current = step;
            }
        }

        if current == prev {
            break;
        }
    }

    current
}
