use crate::grammar::Grammar;

#[derive(Debug, Clone)]
pub struct IdentifierOccurrence {
    pub name: String,
    pub byte_start: usize,
    pub byte_end: usize,
}

pub fn simplify_expression(
    source: &[u8],
    node: &tree_sitter::Node,
    _grammar: &Grammar,
) -> Option<Vec<u8>> {
    let node_text = &source[node.start_byte()..node.end_byte()];
    let result = eval_constant(node_text)?;
    let replacement = result.as_bytes();
    if replacement == node_text {
        return None;
    }
    let mut new_source = Vec::with_capacity(source.len());
    new_source.extend_from_slice(&source[..node.start_byte()]);
    new_source.extend_from_slice(replacement);
    new_source.extend_from_slice(&source[node.end_byte()..]);
    Some(new_source)
}

fn eval_constant(text: &[u8]) -> Option<String> {
    let s = match std::str::from_utf8(text) {
        Ok(s) => s.trim(),
        Err(_) => return None,
    };
    let result = safe_eval(s)?;
    Some(result)
}

fn safe_eval(s: &str) -> Option<String> {
    let allowed =
        |c: char| c.is_ascii_digit() || "+-*/%(). TrueFalsoandornotiIn<>!=\t\n\r".contains(c);
    if !s.chars().all(|c| allowed(c) || c.is_whitespace()) {
        return None;
    }

    // Try integer evaluation
    if let Some(val) = eval_int_expr(s) {
        return Some(val.to_string());
    }
    // Try boolean/comparison evaluation
    if let Some(val) = eval_bool_expr(s) {
        return Some(val.to_string());
    }
    // Try float evaluation
    if let Some(val) = eval_float_expr(s) {
        return Some(val.to_string());
    }
    None
}

fn eval_int_expr(s: &str) -> Option<i64> {
    // Handle comparisons first
    if let Some(val) = eval_int_comparison(s) {
        return Some(val);
    }
    // Handle boolean operators
    if s.contains("and") || s.contains("or") {
        return None;
    }
    // Handle basic arithmetic: try to evaluate simple expressions
    let s = s.trim();
    // Simple integer literal
    if let Ok(v) = s.parse::<i64>() {
        return Some(v);
    }
    // Simple binary operations on integers
    if let Some((left, op, right)) = parse_binary_op(s) {
        let l = eval_int_expr(left.trim())?;
        let r = eval_int_expr(right.trim())?;
        return match op {
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
    // Unary minus
    if let Some(rest) = s.strip_prefix('-') {
        let val = eval_int_expr(rest.trim())?;
        return Some(-val);
    }
    None
}

fn eval_int_comparison(s: &str) -> Option<i64> {
    for op in &["==", "!=", "<=", ">=", "<", ">"] {
        if let Some((left, right)) = s.split_once(op) {
            let l = eval_int_expr(left.trim())?;
            let r = eval_int_expr(right.trim())?;
            let result = match *op {
                "==" => l == r,
                "!=" => l != r,
                "<=" => l <= r,
                ">=" => l >= r,
                "<" => l < r,
                ">" => l > r,
                _ => unreachable!(),
            };
            return Some(if result { 1 } else { 0 });
        }
    }
    None
}

fn eval_bool_expr(s: &str) -> Option<String> {
    let s = s.trim();
    // Boolean literals
    if s == "True" || s == "true" {
        return Some("True".to_string());
    }
    if s == "False" || s == "false" {
        return Some("False".to_string());
    }
    // Boolean comparison
    if let Some(val) = eval_int_comparison(s) {
        return Some(if val != 0 {
            "True".to_string()
        } else {
            "False".to_string()
        });
    }
    // and/or
    if let Some((left, right)) = s.split_once(" and ") {
        let l = eval_bool_expr(left)?;
        let r = eval_bool_expr(right)?;
        let both_true = l == "True" && r == "True";
        return Some(if both_true {
            "True".to_string()
        } else {
            "False".to_string()
        });
    }
    if let Some((left, right)) = s.split_once(" or ") {
        let l = eval_bool_expr(left)?;
        let r = eval_bool_expr(right)?;
        let any_true = l == "True" || r == "True";
        return Some(if any_true {
            "True".to_string()
        } else {
            "False".to_string()
        });
    }
    // not
    if let Some(rest) = s.strip_prefix("not ") {
        let val = eval_bool_expr(rest)?;
        return Some(if val == "True" {
            "False".to_string()
        } else {
            "True".to_string()
        });
    }
    None
}

fn eval_float_expr(s: &str) -> Option<String> {
    let s = s.trim();
    if let Ok(v) = s.parse::<f64>() {
        return Some(format!("{}", v));
    }
    // Handle float division: e.g., "10 / 2" -> "5.0"
    if let Some((left, _op, right)) = parse_binary_op(s) {
        let l = eval_float_val(left.trim())?;
        let r = eval_float_val(right.trim())?;
        if s.contains('/') && r != 0.0 {
            return Some(format!("{}", l / r));
        }
    }
    None
}

fn eval_float_val(s: &str) -> Option<f64> {
    if let Ok(v) = s.parse::<f64>() {
        return Some(v);
    }
    if let Ok(v) = s.parse::<i64>() {
        return Some(v as f64);
    }
    None
}

fn parse_binary_op(s: &str) -> Option<(&str, &str, &str)> {
    let s = s.trim();
    // Find operator not inside parens
    let mut depth = 0;
    let mut last_op_pos = None;
    let mut last_op = "";
    let chars: Vec<char> = s.chars().collect();
    let mut i = 0;
    while i < chars.len() {
        match chars[i] {
            '(' => depth += 1,
            ')' => depth -= 1,
            _ if depth == 0 => {
                for op in &["+", "-", "*", "/", "%"] {
                    if i > 0 && chars[i] == op.chars().next().unwrap() {
                        // Check it's not unary (preceded by operator or start)
                        let prev = chars[i - 1];
                        if prev == '('
                            || prev == ' '
                            || prev == '+'
                            || prev == '-'
                            || prev == '*'
                            || prev == '/'
                            || prev == '%'
                        {
                            // Check it's not part of **, //, etc.
                            if i + 1 < chars.len() && chars[i + 1] == chars[i] {
                                // Skip **, //
                            } else {
                                last_op_pos = Some(i);
                                last_op = op;
                            }
                        }
                    }
                }
            }
            _ => {}
        }
        i += 1;
    }
    if let Some(pos) = last_op_pos {
        let left = &s[..pos];
        let right = &s[pos + last_op.len()..];
        if !left.trim().is_empty() && !right.trim().is_empty() {
            return Some((left, last_op, right));
        }
    }
    None
}

pub fn shorten_identifier(
    source: &[u8],
    _target_name: &str,
    replacement: &str,
    occurrences: &[IdentifierOccurrence],
) -> Vec<u8> {
    if occurrences.is_empty() {
        return source.to_vec();
    }
    let mut sorted_occ = occurrences.to_vec();
    sorted_occ.sort_by(|a, b| b.byte_start.cmp(&a.byte_start));

    let mut new_source = source.to_vec();
    for occ in &sorted_occ {
        let replacement_bytes = replacement.as_bytes();
        new_source.drain(occ.byte_start..occ.byte_end);
        for (i, &byte) in replacement_bytes.iter().enumerate() {
            new_source.insert(occ.byte_start + i, byte);
        }
    }
    new_source
}

pub fn remove_dead_assignment(
    source: &[u8],
    target: &tree_sitter::Node,
    grammar: &Grammar,
) -> Option<Vec<u8>> {
    let kind = target.kind();
    if kind != "assignment" && kind != "augmented_assignment" {
        return None;
    }
    let var_name = extract_var_name(source, target)?;
    if var_name.starts_with('_') {
        return None;
    }
    let tree = parse_tree(source, grammar)?;
    if is_used_after(&var_name, target.end_byte(), tree.root_node()) {
        return None;
    }
    let mut new_source = Vec::with_capacity(source.len());
    new_source.extend_from_slice(&source[..target.start_byte()]);
    new_source.extend_from_slice(&source[target.end_byte()..]);
    Some(new_source)
}

fn extract_var_name(source: &[u8], node: &tree_sitter::Node) -> Option<String> {
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if child.kind() == "identifier" {
            return Some(
                std::str::from_utf8(&source[child.start_byte()..child.end_byte()])
                    .unwrap_or("")
                    .to_string(),
            );
        }
    }
    None
}

fn parse_tree(source: &[u8], grammar: &Grammar) -> Option<tree_sitter::Tree> {
    let mut parser = tree_sitter::Parser::new();
    parser.set_language(grammar.language()).ok()?;
    parser.parse(source, None)
}

fn is_used_after(name: &str, after_byte: usize, node: tree_sitter::Node) -> bool {
    if node.kind() == "identifier" && node.start_byte() >= after_byte {
        let text = node.utf8_text(&[]).unwrap_or("");
        return text == name;
    }
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if is_used_after(name, after_byte, child) {
            return true;
        }
    }
    false
}

pub fn try_escape_transforms(
    source: &[u8],
    grammar: &Grammar,
    is_interesting: &dyn Fn(&[u8]) -> bool,
    max_attempts: usize,
) -> Vec<u8> {
    let mut current = source.to_vec();
    let mut attempts = 0;

    while attempts < max_attempts {
        match apply_one_escape(&current, grammar, is_interesting) {
            Some(transformed) if transformed != current => {
                current = transformed;
                attempts += 1;
            }
            _ => break,
        }
    }
    current
}

fn apply_one_escape(
    source: &[u8],
    grammar: &Grammar,
    is_interesting: &dyn Fn(&[u8]) -> bool,
) -> Option<Vec<u8>> {
    let tree = parse_tree(source, grammar)?;

    // Try expression simplification
    for node in walk_nodes(tree.root_node()) {
        if matches!(
            node.kind(),
            "binary_operator" | "boolean_operator" | "comparison_operator"
        ) {
            if let Some(result) = simplify_expression(source, &node, grammar) {
                if result != source && is_interesting(&result) {
                    return Some(result);
                }
            }
        }
    }

    // Try dead assignment removal
    for node in walk_nodes(tree.root_node()) {
        if node.kind() == "assignment" || node.kind() == "augmented_assignment" {
            if let Some(result) = remove_dead_assignment(source, &node, grammar) {
                if result != source && is_interesting(&result) {
                    return Some(result);
                }
            }
        }
    }

    None
}

fn walk_nodes(node: tree_sitter::Node) -> Vec<tree_sitter::Node> {
    let mut result = vec![node];
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        result.extend(walk_nodes(child));
    }
    result
}
