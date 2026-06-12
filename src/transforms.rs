use std::collections::{HashSet, VecDeque};

use crate::grammar::Grammar;
use crate::parser::{parse_source, reparse_source};
use crate::tree::{NodeInfo, ParseResult, TransformCandidate, TransformKind};
use crate::util::is_blank;

const MAX_BFS_DEPTH: usize = 4;

pub fn bounded_bfs(
    _source: &[u8],
    _root: &NodeInfo,
    target: &NodeInfo,
    grammar: &Grammar,
    predicate: &dyn Fn(&NodeInfo) -> bool,
    max_depth: usize,
) -> Vec<TransformCandidate> {
    let target_supers = grammar.supertypes(&target.kind);
    let mut queue: VecDeque<(usize, NodeInfo)> = VecDeque::new();

    for (idx, child_kind) in target.child_kinds.iter().enumerate() {
        let child = NodeInfo {
            kind: child_kind.clone(),
            byte_start: target.child_byte_starts[idx],
            byte_end: target.child_byte_ends[idx],
            token_count: 0,
            has_errors: false,
            child_kinds: vec![],
            child_byte_starts: vec![],
            child_byte_ends: vec![],
        };
        queue.push_back((1, child));
    }

    let mut found = Vec::new();

    while let Some((depth, node)) = queue.pop_front() {
        if depth > max_depth {
            continue;
        }
        if predicate(&node) {
            let node_supers = grammar.supertypes(&node.kind);
            if !node_supers.is_disjoint(&target_supers) {
                found.push(TransformCandidate {
                    target: target.clone(),
                    kind: TransformKind::Unwrap,
                    unwrap_child_index: Some(-1),
                    child_byte_start: node.byte_start,
                    child_byte_end: node.byte_end,
                });
            }
        }
        for (idx, child_kind) in node.child_kinds.iter().enumerate() {
            let child = NodeInfo {
                kind: child_kind.clone(),
                byte_start: node.child_byte_starts[idx],
                byte_end: node.child_byte_ends[idx],
                token_count: 0,
                has_errors: false,
                child_kinds: vec![],
                child_byte_starts: vec![],
                child_byte_ends: vec![],
            };
            queue.push_back((depth + 1, child));
        }
    }

    found.sort_by(|a, b| b.target.token_count.cmp(&a.target.token_count));
    found
}

pub fn generate_candidates(result: &ParseResult, grammar: &Grammar) -> Vec<TransformCandidate> {
    let mut candidates = Vec::new();
    let root = &result.root_node;

    for node in &result.all_nodes {
        if node.byte_start == root.byte_start && node.byte_end == root.byte_end {
            continue;
        }

        if !node.has_errors && !grammar.is_protected_node(&node.kind) {
            if grammar.is_kleene_node(&node.kind, &node.child_kinds) {
                candidates.push(TransformCandidate {
                    target: node.clone(),
                    kind: TransformKind::Ddmin,
                    unwrap_child_index: None,
                    child_byte_start: 0,
                    child_byte_end: 0,
                });
            } else {
                candidates.push(TransformCandidate {
                    target: node.clone(),
                    kind: TransformKind::Delete,
                    unwrap_child_index: None,
                    child_byte_start: 0,
                    child_byte_end: 0,
                });
            }
        }

        if !node.child_kinds.is_empty() {
            let compatible = grammar.unwrap_compatible_kinds(&node.kind);
            for (idx, child_kind) in node.child_kinds.iter().enumerate() {
                if compatible.contains(child_kind) {
                    candidates.push(TransformCandidate {
                        target: node.clone(),
                        kind: TransformKind::Unwrap,
                        unwrap_child_index: Some(idx as i32),
                        child_byte_start: node.child_byte_starts[idx],
                        child_byte_end: node.child_byte_ends[idx],
                    });
                }
            }

            let bfs = bounded_bfs(
                &result.source_bytes,
                root,
                node,
                grammar,
                &|n: &NodeInfo| !n.has_errors && !grammar.is_protected_node(&n.kind),
                MAX_BFS_DEPTH,
            );
            candidates.extend(bfs);
        }
    }

    candidates
}

pub fn apply_delete(source: &[u8], target: &NodeInfo) -> Vec<u8> {
    let mut new_source = Vec::with_capacity(source.len());
    new_source.extend_from_slice(&source[..target.byte_start]);
    new_source.extend_from_slice(&source[target.byte_end..]);
    new_source
}

pub fn apply_unwrap(
    source: &[u8],
    target: &NodeInfo,
    child_byte_start: usize,
    child_byte_end: usize,
) -> Vec<u8> {
    let mut new_source = Vec::with_capacity(source.len());
    new_source.extend_from_slice(&source[..target.byte_start]);
    new_source.extend_from_slice(&source[child_byte_start..child_byte_end]);
    new_source.extend_from_slice(&source[target.byte_end..]);
    new_source
}

fn remove_children(
    source: &[u8],
    _target: &NodeInfo,
    keep_indices: &[usize],
    named_children: &[(usize, usize, usize)],
) -> Vec<u8> {
    let mut remove_ranges: Vec<(usize, usize)> = named_children
        .iter()
        .filter(|(idx, _, _)| !keep_indices.contains(idx))
        .map(|&(_, start, end)| (start, end))
        .collect();
    remove_ranges.sort_by(|a, b| b.0.cmp(&a.0));

    let mut new_source = source.to_vec();
    for (start, end) in remove_ranges {
        new_source.drain(start..end);
    }
    new_source
}

pub fn apply_ddmin(
    source: &[u8],
    target: &NodeInfo,
    grammar: &Grammar,
    is_interesting: &dyn Fn(&[u8]) -> bool,
    base_error_count: Option<usize>,
    strict: bool,
) -> Option<(Vec<u8>, ParseResult)> {
    let keyword_kinds: HashSet<&str> = [
        "def", "class", "if", "elif", "else", "for", "while", "try", "except", "finally", "with",
        "return", "import", "from", "as", "lambda", "yield", "assert", "del", "raise", "pass",
        "break", "continue", "global", "nonlocal", "async", "await", "match", "case", "(", ")",
        "[", "]", "{", "}", ",", ":", ";", ".", "->", "=", "+=", "-=", "*=", "/=", "//=", "%=",
        "**=", ">>=", "<<=", "&=", "^=", "|=", "and", "or", "not", "in", "is", "is not", "not in",
    ]
    .iter()
    .cloned()
    .collect();

    let named_children: Vec<(usize, usize, usize)> = target
        .child_kinds
        .iter()
        .enumerate()
        .filter(|(_, kind)| !keyword_kinds.contains(kind.as_str()))
        .map(|(i, _)| (i, target.child_byte_starts[i], target.child_byte_ends[i]))
        .collect();

    if named_children.len() < 2 {
        return None;
    }

    let removable: Vec<usize> = (0..named_children.len()).collect();

    fn ddmin_recursive(
        source: &[u8],
        _target: &NodeInfo,
        grammar: &Grammar,
        is_interesting: &dyn Fn(&[u8]) -> bool,
        base_error_count: Option<usize>,
        strict: bool,
        named_children: &[(usize, usize, usize)],
        elems: &[usize],
    ) -> Vec<usize> {
        if elems.len() <= 1 {
            return elems.to_vec();
        }
        let mut n = 2;
        while n <= elems.len() {
            let chunk_size = std::cmp::max(1, elems.len() / n);
            let mut i = 0;
            while i < elems.len() {
                let partition: Vec<usize> =
                    elems[i..std::cmp::min(i + chunk_size, elems.len())].to_vec();
                let complement: Vec<usize> = elems
                    .iter()
                    .filter(|e| !partition.contains(e))
                    .copied()
                    .collect();
                if complement.is_empty() {
                    i += chunk_size;
                    continue;
                }
                let new_source = remove_children(source, _target, &complement, named_children);
                if new_source == source || is_blank(&new_source) {
                    i += chunk_size;
                    continue;
                }
                if check_valid(&new_source, grammar, base_error_count, strict) {
                    if is_interesting(&new_source) {
                        return ddmin_recursive(
                            source,
                            _target,
                            grammar,
                            is_interesting,
                            base_error_count,
                            strict,
                            named_children,
                            &complement,
                        );
                    }
                }
                i += chunk_size;
            }
            n *= 2;
        }
        elems.to_vec()
    }

    let remaining = ddmin_recursive(
        source,
        target,
        grammar,
        is_interesting,
        base_error_count,
        strict,
        &named_children,
        &removable,
    );

    if remaining.len() == named_children.len() {
        return None;
    }

    let new_source = remove_children(source, target, &remaining, &named_children);
    if new_source == source || is_blank(&new_source) {
        return None;
    }
    if !check_valid(&new_source, grammar, base_error_count, strict) {
        return None;
    }
    let new_result = parse_source(&new_source, grammar);
    Some((new_source, new_result))
}

fn check_valid(
    source: &[u8],
    grammar: &Grammar,
    base_error_count: Option<usize>,
    strict: bool,
) -> bool {
    let result = parse_source(source, grammar);
    let base = base_error_count.unwrap_or_else(|| result_error_count(source, grammar));
    if strict {
        result.error_node_count == 0
    } else {
        result.error_node_count <= base
    }
}

pub fn result_error_count(source: &[u8], grammar: &Grammar) -> usize {
    parse_source(source, grammar).error_node_count
}

pub fn apply_transform(
    source: &[u8],
    candidate: &TransformCandidate,
    grammar: &Grammar,
    root_node: Option<&NodeInfo>,
    base_error_count: Option<usize>,
    old_result: Option<&ParseResult>,
    strict: bool,
    is_interesting: Option<&dyn Fn(&[u8]) -> bool>,
) -> Option<(Vec<u8>, ParseResult)> {
    let target = &candidate.target;

    if let Some(root) = root_node {
        if target.byte_start == root.byte_start && target.byte_end == root.byte_end {
            return None;
        }
    }

    if target.byte_start == target.byte_end {
        return None;
    }

    let new_source = match candidate.kind {
        TransformKind::Delete => apply_delete(source, target),
        TransformKind::Unwrap => {
            let idx = match candidate.unwrap_child_index {
                Some(i) => i,
                None => return None,
            };
            if idx >= 0 {
                if idx as usize >= target.child_kinds.len() {
                    return None;
                }
            }
            apply_unwrap(
                source,
                target,
                candidate.child_byte_start,
                candidate.child_byte_end,
            )
        }
        TransformKind::Ddmin => {
            let interesting = match is_interesting {
                Some(f) => f,
                None => return None,
            };
            return apply_ddmin(
                source,
                target,
                grammar,
                interesting,
                base_error_count,
                strict,
            );
        }
    };

    if new_source == source {
        return None;
    }
    if is_blank(&new_source) {
        return None;
    }

    let new_result = if old_result.is_some() {
        reparse_source(&new_source, grammar)
    } else {
        parse_source(&new_source, grammar)
    };

    let base = match base_error_count {
        Some(b) => b,
        None => result_error_count(source, grammar),
    };

    if strict {
        if new_result.error_node_count > 0 {
            return None;
        }
    } else if new_result.error_node_count > base {
        return None;
    }

    Some((new_source, new_result))
}
