use crate::grammar::Grammar;
use crate::tree::{NodeInfo, ParseResult};

fn count_tokens(node: &tree_sitter::Node) -> usize {
    if node.child_count() == 0 {
        return 1;
    }
    let mut count = 0;
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        count += count_tokens(&child);
    }
    count
}

fn has_errors(node: &tree_sitter::Node, grammar: &Grammar) -> bool {
    if grammar.is_error_node(node.kind()) {
        return true;
    }
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        if has_errors(&child, grammar) {
            return true;
        }
    }
    false
}

fn child_kinds(node: &tree_sitter::Node) -> Vec<String> {
    let mut kinds = Vec::with_capacity(node.child_count());
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        kinds.push(child.kind().to_string());
    }
    kinds
}

fn child_byte_starts(node: &tree_sitter::Node) -> Vec<usize> {
    let mut starts = Vec::with_capacity(node.child_count());
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        starts.push(child.start_byte());
    }
    starts
}

fn child_byte_ends(node: &tree_sitter::Node) -> Vec<usize> {
    let mut ends = Vec::with_capacity(node.child_count());
    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        ends.push(child.end_byte());
    }
    ends
}

fn node_info(node: &tree_sitter::Node, grammar: &Grammar) -> NodeInfo {
    let errs = has_errors(node, grammar);
    NodeInfo {
        kind: node.kind().to_string(),
        byte_start: node.start_byte(),
        byte_end: node.end_byte(),
        token_count: count_tokens(node),
        has_errors: errs,
        child_kinds: child_kinds(node),
        child_byte_starts: child_byte_starts(node),
        child_byte_ends: child_byte_ends(node),
    }
}

fn walk_tree(node: &tree_sitter::Node, grammar: &Grammar) -> (Vec<NodeInfo>, usize) {
    let mut nodes = Vec::new();
    let mut error_count = 0usize;

    let info = node_info(node, grammar);
    if info.has_errors {
        error_count += 1;
    }
    nodes.push(info);

    let mut cursor = node.walk();
    for child in node.children(&mut cursor) {
        let (child_nodes, child_errors) = walk_tree(&child, grammar);
        error_count += child_errors;
        nodes.extend(child_nodes);
    }

    (nodes, error_count)
}

pub fn parse_source(source: &[u8], grammar: &Grammar) -> ParseResult {
    let mut parser = tree_sitter::Parser::new();
    parser.set_language(grammar.language()).unwrap();
    let tree = parser.parse(source, None).unwrap();

    let (all_nodes, error_count) = walk_tree(&tree.root_node(), grammar);

    let root = if !all_nodes.is_empty() {
        all_nodes[0].clone()
    } else {
        NodeInfo {
            kind: "ERROR".to_string(),
            byte_start: 0,
            byte_end: 0,
            token_count: 0,
            has_errors: true,
            child_kinds: vec![],
            child_byte_starts: vec![],
            child_byte_ends: vec![],
        }
    };

    let mut sorted = all_nodes;
    sorted.sort_by(|a, b| b.token_count.cmp(&a.token_count));

    ParseResult {
        source_bytes: source.to_vec(),
        root_node: root,
        all_nodes: sorted,
        error_node_count: error_count,
    }
}

pub fn reparse_source(new_source: &[u8], grammar: &Grammar) -> ParseResult {
    parse_source(new_source, grammar)
}

pub fn has_syntax_errors(result: &ParseResult) -> bool {
    result.error_node_count > 0
}
