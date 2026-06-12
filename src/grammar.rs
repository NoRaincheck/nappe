use std::collections::{HashMap, HashSet};
use std::path::Path;

pub struct Grammar {
    language: tree_sitter::Language,
    name: String,
    field_cache: HashMap<(String, usize), String>,
}

const ERROR_KINDS: &[&str] = &["ERROR", "MISSING", "UNEXPECTED_TOKEN"];
const PROTECTED_KINDS: &[&str] = &["comment"];
const KEYWORD_KINDS: &[&str] = &[
    "def", "class", "if", "elif", "else", "for", "while", "try", "except", "finally", "with",
    "return", "import", "from", "as", "lambda", "yield", "assert", "del", "raise", "pass", "break",
    "continue", "global", "nonlocal", "async", "await", "match", "case", "(", ")", "[", "]", "{",
    "}", ",", ":", ";", ".", "->", "=", "+=", "-=", "*=", "/=", "//=", "%=", "**=", ">>=", "<<=",
    "&=", "^=", "|=", "and", "or", "not", "in", "is", "is not", "not in",
];

impl Grammar {
    pub fn new(lang_fn: tree_sitter_language::LanguageFn, name: &str) -> Self {
        let language = tree_sitter::Language::new(lang_fn);
        let mut grammar = Grammar {
            language,
            name: name.to_string(),
            field_cache: HashMap::new(),
        };
        grammar.build_field_cache();
        grammar
    }

    pub fn language(&self) -> &tree_sitter::Language {
        &self.language
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn is_error_node(&self, kind: &str) -> bool {
        ERROR_KINDS.contains(&kind)
    }

    pub fn is_protected_node(&self, kind: &str) -> bool {
        PROTECTED_KINDS.contains(&kind)
    }

    pub fn unwrap_compatible_kinds(&self, node_kind: &str) -> HashSet<String> {
        self.subtypes(node_kind)
    }

    pub fn subtypes(&self, kind: &str) -> HashSet<String> {
        let kind_id = self.language.id_for_node_kind(kind, true);
        if kind_id == u16::MAX {
            return HashSet::from([kind.to_string()]);
        }
        let mut result = HashSet::from([kind.to_string()]);
        // Collect all supertypes that contain this kind
        for &sup_id in self.language.supertypes() {
            let sub_ids = self.language.subtypes_for_supertype(sup_id);
            if sub_ids.contains(&kind_id) {
                if let Some(name) = self.language.node_kind_for_id(sup_id) {
                    result.insert(name.to_string());
                }
            }
        }
        result
    }

    pub fn supertypes(&self, kind: &str) -> HashSet<String> {
        let kind_id = self.language.id_for_node_kind(kind, true);
        if kind_id == u16::MAX {
            return HashSet::from([kind.to_string()]);
        }
        let mut result = HashSet::from([kind.to_string()]);
        for &sup_id in self.language.supertypes() {
            let sub_ids = self.language.subtypes_for_supertype(sup_id);
            if sub_ids.contains(&kind_id) {
                if let Some(name) = self.language.node_kind_for_id(sup_id) {
                    result.insert(name.to_string());
                }
            }
        }
        result
    }

    pub fn is_kleene_node(&self, _node_kind: &str, child_kinds: &[String]) -> bool {
        let named: Vec<&str> = child_kinds
            .iter()
            .filter(|k| !KEYWORD_KINDS.contains(&k.as_str()))
            .map(|k| k.as_str())
            .collect();
        named.len() >= 2 && named.iter().collect::<HashSet<_>>().len() == 1
    }

    pub fn is_subtype(&self, child_kind: &str, parent_kind: &str) -> bool {
        self.subtypes(parent_kind).contains(child_kind)
    }

    pub fn field_name_for_child(&self, parent_kind: &str, child_index: usize) -> Option<&str> {
        self.field_cache
            .get(&(parent_kind.to_string(), child_index))
            .map(|s| s.as_str())
    }

    fn build_field_cache(&mut self) {
        let mut parser = tree_sitter::Parser::new();
        parser.set_language(&self.language).unwrap();

        let sample = b"def f(x, y=1):\n\
                        \x20\x20\x20\x20return x + y\n\
                        if True:\n\
                        \x20\x20\x20\x20x = 1\n\
                        class C:\n\
                        \x20\x20\x20\x20def m(self): pass\n\
                        x = [1]\n\
                        y = {1: 2}\n\
                        z = (1,)\n\
                        for i in x:\n\
                        \x20\x20\x20\x20pass\n\
                        while True:\n\
                        \x20\x20\x20\x20break\n";

        if let Some(tree) = parser.parse(sample, None) {
            Self::walk_fields(&tree.root_node(), &mut self.field_cache);
        }
    }

    fn walk_fields(node: &tree_sitter::Node, cache: &mut HashMap<(String, usize), String>) {
        for i in 0..node.child_count() {
            if let Some(fname) = node.field_name_for_child(i as u32) {
                cache.insert((node.kind().to_string(), i), fname.to_string());
            }
        }
        let mut cursor = node.walk();
        for child in node.named_children(&mut cursor) {
            Self::walk_fields(&child, cache);
        }
    }
}

const EXTENSION_MAP: &[(&str, &str)] = &[
    (".py", "python"),
    (".pyi", "python"),
    (".js", "javascript"),
    (".mjs", "javascript"),
    (".cjs", "javascript"),
    (".ts", "typescript"),
    (".tsx", "typescript"),
    (".rs", "rust"),
    (".go", "go"),
    (".c", "c"),
    (".h", "c"),
    (".cpp", "cpp"),
    (".cc", "cpp"),
    (".cxx", "cpp"),
];

pub fn detect_language(path: &str) -> Result<String, String> {
    let ext = Path::new(path)
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| format!(".{}", e))
        .ok_or_else(|| "Cannot detect language from extension".to_string())?;

    EXTENSION_MAP
        .iter()
        .find(|(e, _)| *e == ext)
        .map(|(_, lang)| lang.to_string())
        .ok_or_else(|| format!("Cannot detect language from extension '{}'", ext))
}

pub fn load_grammar(lang_name: &str) -> Result<Grammar, String> {
    match lang_name {
        "python" => Ok(Grammar::new(tree_sitter_python::LANGUAGE, "python")),
        "javascript" => Ok(Grammar::new(tree_sitter_javascript::LANGUAGE, "javascript")),
        "typescript" => Ok(Grammar::new(
            tree_sitter_typescript::LANGUAGE_TYPESCRIPT,
            "typescript",
        )),
        "rust" => Ok(Grammar::new(tree_sitter_rust::LANGUAGE, "rust")),
        "go" => Ok(Grammar::new(tree_sitter_go::LANGUAGE, "go")),
        "c" => Ok(Grammar::new(tree_sitter_c::LANGUAGE, "c")),
        "cpp" => Ok(Grammar::new(tree_sitter_cpp::LANGUAGE, "cpp")),
        _ => Err(format!("Unsupported language: {}", lang_name)),
    }
}
