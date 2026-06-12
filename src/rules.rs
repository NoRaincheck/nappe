use std::collections::HashMap;
use std::sync::LazyLock;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FixSafety {
    Safe,
    Unsafe,
}

impl FixSafety {
    pub fn as_str(&self) -> &str {
        match self {
            FixSafety::Safe => "safe",
            FixSafety::Unsafe => "unsafe",
        }
    }
}

#[derive(Debug, Clone)]
pub struct Rule {
    pub code: &'static str,
    pub description: &'static str,
    pub safety: FixSafety,
}

#[derive(Debug)]
pub struct Suggestion {
    pub file_path: String,
    pub line: usize,
    pub col: usize,
    pub rule: &'static Rule,
    pub old_source: Vec<u8>,
    pub new_source: Vec<u8>,
    pub context: String,
}

pub static RULES: LazyLock<HashMap<&'static str, Rule>> = LazyLock::new(|| {
    let mut m = HashMap::new();
    m.insert(
        "RED100",
        Rule {
            code: "RED100",
            description: "Dead function (no callers)",
            safety: FixSafety::Unsafe,
        },
    );
    m.insert(
        "RED101",
        Rule {
            code: "RED101",
            description: "Dead class (no instantiations)",
            safety: FixSafety::Unsafe,
        },
    );
    m.insert(
        "RED102",
        Rule {
            code: "RED102",
            description: "Unused variable assignment",
            safety: FixSafety::Unsafe,
        },
    );
    m.insert(
        "RED200",
        Rule {
            code: "RED200",
            description: "Constant expression simplification",
            safety: FixSafety::Safe,
        },
    );
    m.insert(
        "RED201",
        Rule {
            code: "RED201",
            description: "Redundant parentheses",
            safety: FixSafety::Safe,
        },
    );
    m.insert(
        "RED202",
        Rule {
            code: "RED202",
            description: "Unnecessary semicolon",
            safety: FixSafety::Safe,
        },
    );
    m.insert(
        "RED203",
        Rule {
            code: "RED203",
            description: "Trailing whitespace",
            safety: FixSafety::Safe,
        },
    );
    m.insert(
        "RED204",
        Rule {
            code: "RED204",
            description: "Redundant newline",
            safety: FixSafety::Safe,
        },
    );
    m
});
