use std::collections::HashMap;

pub struct Cache {
    results: HashMap<[u8; 16], bool>,
}

impl Cache {
    pub fn new() -> Self {
        Cache {
            results: HashMap::new(),
        }
    }

    pub fn get(&self, source: &[u8]) -> Option<bool> {
        self.results.get(&key(source)).copied()
    }

    pub fn set(&mut self, source: &[u8], result: bool) {
        self.results.insert(key(source), result);
    }
}

fn key(source: &[u8]) -> [u8; 16] {
    let hash = blake3::hash(source);
    let mut out = [0u8; 16];
    out.copy_from_slice(&hash.as_bytes()[..16]);
    out
}
