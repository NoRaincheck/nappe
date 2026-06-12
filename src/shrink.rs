use std::fs;
use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};
use std::time::Instant;

use crate::cache::Cache;
use crate::grammar::{detect_language, load_grammar, Grammar};
use crate::parser::parse_source;
use crate::transforms::{apply_transform, generate_candidates};

pub struct ShrinkResult {
    pub source: Vec<u8>,
    pub tests_run: usize,
    pub elapsed_seconds: f64,
    pub output_path: Option<String>,
}

pub struct ShrinkReducer {
    grammar: Grammar,
    test_command: String,
    cmd_parts: Vec<String>,
    timeout: f64,
    max_time: Option<f64>,
    max_tests: Option<usize>,
    parallelism: usize,
    verbose: bool,
    quiet: bool,
    cache: Cache,
    tests_run: usize,
}

impl ShrinkReducer {
    pub fn new(
        grammar: Grammar,
        test_command: String,
        timeout: f64,
        max_time: Option<f64>,
        max_tests: Option<usize>,
        parallelism: usize,
        verbose: bool,
        quiet: bool,
    ) -> Self {
        let cmd_parts = shell_words_split(&test_command);
        ShrinkReducer {
            grammar,
            test_command,
            cmd_parts,
            timeout,
            max_time,
            max_tests,
            parallelism,
            verbose,
            quiet,
            cache: Cache::new(),
            tests_run: 0,
        }
    }

    pub fn reduce(&mut self, source: &[u8], filename: Option<&str>) -> ShrinkResult {
        let start_time = Instant::now();
        let mut current_source = source.to_vec();
        self.tests_run = 0;

        while !self.should_stop(start_time) {
            let result = parse_source(&current_source, &self.grammar);
            let candidates = generate_candidates(&result, &self.grammar);

            if candidates.is_empty() {
                break;
            }

            let base_error_count = result.error_node_count;
            let mut accepted = false;

            for candidate in &candidates {
                if self.should_stop(start_time) {
                    break;
                }

                let new = apply_transform(
                    &current_source,
                    candidate,
                    &self.grammar,
                    Some(&result.root_node),
                    Some(base_error_count),
                    None,
                    false,
                    None,
                );

                if let Some((new_source, _)) = new {
                    if self.is_interesting(&new_source, filename) {
                        if self.verbose {
                            eprintln!(
                                "accepted {} at bytes {}-{}",
                                candidate.kind,
                                candidate.target.byte_start,
                                candidate.target.byte_end
                            );
                        }
                        current_source = new_source;
                        accepted = true;
                        break;
                    } else if self.verbose {
                        eprintln!(
                            "rejected {} at bytes {}-{}",
                            candidate.kind, candidate.target.byte_start, candidate.target.byte_end
                        );
                    }
                }
            }

            if !accepted {
                break;
            }
        }

        let elapsed = start_time.elapsed().as_secs_f64();
        ShrinkResult {
            source: current_source,
            tests_run: self.tests_run,
            elapsed_seconds: elapsed,
            output_path: filename.map(|s| s.to_string()),
        }
    }

    fn is_interesting(&mut self, source: &[u8], _filename: Option<&str>) -> bool {
        if let Some(cached) = self.cache.get(source) {
            return cached;
        }

        self.tests_run += 1;

        let temp = tempfile::NamedTempFile::new();
        let is_interesting = match temp {
            Ok(mut f) => {
                let _ = f.write_all(source);
                let temp_path = f.path().to_owned();
                drop(f);

                let mut args = self.cmd_parts.clone();
                args.push(temp_path.to_str().unwrap().to_string());

                let result = Command::new(&args[0])
                    .args(&args[1..])
                    .stdin(Stdio::piped())
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .spawn()
                    .and_then(|mut child| {
                        if let Some(ref mut stdin) = child.stdin {
                            let _ = stdin.write_all(source);
                        }
                        child.wait()
                    });

                let _ = std::fs::remove_file(&temp_path);

                match result {
                    Ok(status) => status.success(),
                    Err(_) => false,
                }
            }
            Err(_) => false,
        };

        self.cache.set(source, is_interesting);
        is_interesting
    }

    fn should_stop(&self, start_time: Instant) -> bool {
        if let Some(max_tests) = self.max_tests {
            if self.tests_run >= max_tests {
                return true;
            }
        }
        if let Some(max_time) = self.max_time {
            if start_time.elapsed().as_secs_f64() >= max_time {
                return true;
            }
        }
        false
    }
}

fn shell_words_split(s: &str) -> Vec<String> {
    let mut result = Vec::new();
    let mut current = String::new();
    let mut in_single = false;
    let mut in_double = false;
    let mut chars = s.chars().peekable();

    while let Some(c) = chars.next() {
        match c {
            '\'' if !in_double => {
                in_single = !in_single;
            }
            '"' if !in_single => {
                in_double = !in_double;
            }
            ' ' | '\t' if !in_single && !in_double => {
                if !current.is_empty() {
                    result.push(current.clone());
                    current.clear();
                }
            }
            '\\' if !in_single => {
                if let Some(next) = chars.next() {
                    current.push(next);
                }
            }
            _ => {
                current.push(c);
            }
        }
    }
    if !current.is_empty() {
        result.push(current);
    }
    result
}

pub fn run_shrink(
    test_command: &str,
    filename: &str,
    timeout: f64,
    max_time: Option<f64>,
    max_tests: Option<usize>,
    parallelism: usize,
    backup: Option<&str>,
    verbose: bool,
    quiet: bool,
) -> i32 {
    let input_path = if Path::new(filename).is_absolute() {
        filename.to_string()
    } else {
        std::env::current_dir()
            .map(|d| d.join(filename).to_string_lossy().to_string())
            .unwrap_or_else(|_| filename.to_string())
    };

    if !Path::new(&input_path).exists() {
        eprintln!("Error: file not found: {}", input_path);
        return 1;
    }

    let source = match fs::read(&input_path) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("Error reading {}: {}", input_path, e);
            return 1;
        }
    };

    let lang = match detect_language(&input_path) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("Error: {}", e);
            return 1;
        }
    };

    let grammar = match load_grammar(&lang) {
        Ok(g) => g,
        Err(e) => {
            eprintln!("Error: {}", e);
            return 1;
        }
    };

    let backup_ext = backup.unwrap_or("bak");
    let backup_path = format!("{}.{}", input_path, backup_ext);
    if let Err(e) = fs::write(&backup_path, &source) {
        eprintln!("Warning: could not create backup: {}", e);
    }

    let mut reducer = ShrinkReducer::new(
        grammar,
        test_command.to_string(),
        timeout,
        max_time,
        max_tests,
        parallelism,
        verbose,
        quiet,
    );

    let original_size = source.len();
    let result = reducer.reduce(&source, Some(&input_path));

    if let Err(e) = fs::write(&input_path, &result.source) {
        eprintln!("Error writing {}: {}", input_path, e);
        return 1;
    }

    if !quiet {
        let reduced_size = result.source.len();
        let pct = if original_size > 0 {
            (1.0 - reduced_size as f64 / original_size as f64) * 100.0
        } else {
            0.0
        };
        let elapsed = result.elapsed_seconds;
        let time_str = if elapsed < 60.0 {
            format!("{:.1}s", elapsed)
        } else {
            let mins = elapsed as u64 / 60;
            let secs = elapsed as u64 % 60;
            format!("{}m {}s", mins, secs)
        };
        eprintln!(
            "Reduced {} -> {} bytes ({:.0}% reduction) in {} ({} tests)",
            original_size, reduced_size, pct, time_str, result.tests_run
        );
    }

    0
}
