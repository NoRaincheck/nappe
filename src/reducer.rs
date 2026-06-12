use std::cell::RefCell;
use std::io::Write;
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::time::Instant;

use crate::cache::Cache;
use crate::escapes::try_escape_transforms;
use crate::grammar::Grammar;
use crate::parser::parse_source;
use crate::token_reduce::token_reduce;
use crate::transforms::{apply_transform, generate_candidates};
use crate::tree::ParseResult;

pub struct ReduceResult {
    pub source: Vec<u8>,
    pub tests_run: usize,
    pub elapsed_seconds: f64,
}

struct TestContext {
    grammar: Arc<Grammar>,
    cache: Cache,
    tests_run: usize,
    auto: bool,
    test_spec: Option<String>,
    cmd_parts: Option<Vec<String>>,
}

impl TestContext {
    fn is_interesting(&mut self, source: &[u8]) -> bool {
        if let Some(cached) = self.cache.get(source) {
            return cached;
        }

        self.tests_run += 1;

        let is_interesting = if self.auto {
            let result = parse_source(source, &self.grammar);
            result.error_node_count == 0
        } else if self.test_spec.is_some() {
            self.is_interesting_pytest(source)
        } else {
            self.is_interesting_command(source)
        };

        self.cache.set(source, is_interesting);
        is_interesting
    }

    fn is_interesting_pytest(&self, source: &[u8]) -> bool {
        let test_spec = match &self.test_spec {
            Some(s) => s,
            None => return false,
        };

        let mut temp = match tempfile::NamedTempFile::new() {
            Ok(f) => f,
            Err(_) => return false,
        };
        if temp.write_all(source).is_err() {
            return false;
        }
        let temp_path = temp.path().to_owned();
        drop(temp);

        let result = Command::new("python3")
            .args([
                "-m",
                "pytest",
                temp_path.to_str().unwrap(),
                test_spec,
                "-x",
                "--tb=no",
                "-q",
            ])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .output();

        let _ = std::fs::remove_file(&temp_path);

        match result {
            Ok(output) => output.status.success(),
            Err(_) => false,
        }
    }

    fn is_interesting_command(&self, source: &[u8]) -> bool {
        let cmd_parts = match &self.cmd_parts {
            Some(p) => p,
            None => return false,
        };

        if cmd_parts.is_empty() {
            return false;
        }

        let result = Command::new(&cmd_parts[0])
            .args(&cmd_parts[1..])
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .and_then(|mut child| {
                if let Some(ref mut stdin) = child.stdin {
                    stdin.write_all(source)?;
                }
                child.wait()
            });

        match result {
            Ok(status) => status.success(),
            Err(_) => false,
        }
    }
}

pub struct Reducer {
    grammar: Arc<Grammar>,
    test_spec: Option<String>,
    test_command: Option<String>,
    auto: bool,
    max_time: Option<f64>,
    max_tests: Option<usize>,
    jobs: usize,
    verbose: bool,
    quiet: bool,
    strict: bool,
    cmd_parts: Option<Vec<String>>,
}

impl Reducer {
    pub fn new(
        grammar: Grammar,
        test_spec: Option<String>,
        test_command: Option<String>,
        auto: bool,
        max_time: Option<f64>,
        max_tests: Option<usize>,
        jobs: usize,
        verbose: bool,
        quiet: bool,
        strict: bool,
    ) -> Self {
        let cmd_parts = test_command
            .as_ref()
            .map(|cmd| shell_words::split(cmd).unwrap_or_else(|_| vec![cmd.clone()]));
        Reducer {
            grammar: Arc::new(grammar),
            test_spec,
            test_command,
            auto,
            max_time,
            max_tests,
            jobs,
            verbose,
            quiet,
            strict,
            cmd_parts,
        }
    }

    pub fn reduce(&mut self, source: &[u8]) -> ReduceResult {
        let start_time = Instant::now();
        let mut current_source = source.to_vec();
        let mut current_result: Option<ParseResult> = None;

        let ctx = RefCell::new(TestContext {
            grammar: Arc::clone(&self.grammar),
            cache: Cache::new(),
            tests_run: 0,
            auto: self.auto,
            test_spec: self.test_spec.clone(),
            cmd_parts: self.cmd_parts.clone(),
        });

        let mut prev_size: Option<usize> = None;
        let max_tests = self.max_tests;
        let max_time = self.max_time;
        let jobs = self.jobs;
        let grammar = Arc::clone(&self.grammar);
        let strict = self.strict;
        let quiet = self.quiet;

        let should_stop = || -> bool {
            let c = ctx.borrow();
            if let Some(mt) = max_tests {
                if c.tests_run >= mt {
                    return true;
                }
            }
            if let Some(mt) = max_time {
                if start_time.elapsed().as_secs_f64() >= mt {
                    return true;
                }
            }
            false
        };

        for escape_round in 0..2 {
            while !should_stop() {
                if current_result.is_none()
                    || current_result.as_ref().map(|r| &r.source_bytes) != Some(&current_source)
                {
                    current_result = Some(parse_source(&current_source, &grammar));
                }
                let result = current_result.as_ref().unwrap();
                let candidates = generate_candidates(result, &grammar);

                if candidates.is_empty() {
                    break;
                }

                let base_error_count = result.error_node_count;
                let mut accepted = false;

                for batch_start in (0..candidates.len()).step_by(jobs.max(1)) {
                    if should_stop() {
                        break;
                    }

                    let batch_end = (batch_start + jobs).min(candidates.len());
                    let mut batch: Vec<(usize, Vec<u8>, ParseResult)> = Vec::new();

                    for candidate in &candidates[batch_start..batch_end] {
                        if should_stop() {
                            break;
                        }

                        let root_node = &current_result.as_ref().unwrap().root_node;
                        let transform_result = apply_transform(
                            &current_source,
                            candidate,
                            &grammar,
                            Some(root_node),
                            Some(base_error_count),
                            current_result.as_ref(),
                            strict,
                            None,
                        );

                        if let Some((new_source, new_result)) = transform_result {
                            batch.push((batch.len(), new_source, new_result));
                        }
                    }

                    if batch.is_empty() {
                        continue;
                    }

                    let sources: Vec<&[u8]> = batch.iter().map(|(_, s, _)| s.as_slice()).collect();
                    let test_results: Vec<bool> = sources
                        .iter()
                        .map(|s| ctx.borrow_mut().is_interesting(s))
                        .collect();

                    for ((_, new_source, new_result), is_interesting) in
                        batch.into_iter().zip(test_results)
                    {
                        if is_interesting {
                            if !quiet {
                                let elapsed = start_time.elapsed().as_secs_f64();
                                let prev = prev_size.unwrap_or(current_source.len());
                                let change =
                                    (new_source.len() as f64 - prev as f64) / prev as f64 * 100.0;
                                let tests = ctx.borrow().tests_run;
                                eprintln!(
                                    "[{:.1}s] {} -> {} bytes ({:+.1}%) | {} tests",
                                    elapsed,
                                    prev,
                                    new_source.len(),
                                    change,
                                    tests
                                );
                            }
                            prev_size = Some(current_source.len());
                            current_source = new_source;
                            current_result = Some(new_result);
                            accepted = true;
                            break;
                        }
                    }

                    if accepted {
                        break;
                    }
                }

                if !accepted {
                    break;
                }
            }

            if escape_round == 0 && !should_stop() {
                let escaped = try_escape_transforms(
                    &current_source,
                    &grammar,
                    &|s| ctx.borrow_mut().is_interesting(s),
                    50,
                );
                if escaped != current_source {
                    prev_size = Some(current_source.len());
                    current_source = escaped;
                    current_result = None;
                } else {
                    break;
                }
            } else {
                break;
            }
        }

        if !should_stop() {
            let token_result = token_reduce(&current_source, &grammar, &|s| {
                ctx.borrow_mut().is_interesting(s)
            });
            if token_result != current_source {
                current_source = token_result;
            }
        }

        let elapsed = start_time.elapsed().as_secs_f64();
        let final_size = current_source.len();
        let tests_run = ctx.borrow().tests_run;

        if !quiet {
            let pct = if source.len() > 0 {
                (1.0 - final_size as f64 / source.len() as f64) * 100.0
            } else {
                0.0
            };
            eprintln!(
                "Reduced: {} -> {} bytes ({:.1}% reduction) | {} tests | {:.1}s",
                source.len(),
                final_size,
                pct,
                tests_run,
                elapsed
            );
        }

        ReduceResult {
            source: current_source,
            tests_run,
            elapsed_seconds: elapsed,
        }
    }
}

mod shell_words {
    pub fn split(s: &str) -> Result<Vec<String>, ()> {
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
        Ok(result)
    }
}
