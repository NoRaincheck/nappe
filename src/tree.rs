use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TransformKind {
    Delete,
    Unwrap,
    Ddmin,
}

impl fmt::Display for TransformKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            TransformKind::Delete => write!(f, "delete"),
            TransformKind::Unwrap => write!(f, "unwrap"),
            TransformKind::Ddmin => write!(f, "ddmin"),
        }
    }
}

#[derive(Debug, Clone)]
pub struct NodeInfo {
    pub kind: String,
    pub byte_start: usize,
    pub byte_end: usize,
    pub token_count: usize,
    pub has_errors: bool,
    pub child_kinds: Vec<String>,
    pub child_byte_starts: Vec<usize>,
    pub child_byte_ends: Vec<usize>,
}

#[derive(Debug, Clone)]
pub struct TransformCandidate {
    pub target: NodeInfo,
    pub kind: TransformKind,
    pub unwrap_child_index: Option<i32>,
    pub child_byte_start: usize,
    pub child_byte_end: usize,
}

#[derive(Debug)]
pub struct ParseResult {
    pub source_bytes: Vec<u8>,
    pub root_node: NodeInfo,
    pub all_nodes: Vec<NodeInfo>,
    pub error_node_count: usize,
}
