use std::env;
use std::fs;
use std::path::PathBuf;
use std::process;

use clap::{Parser, Subcommand};

use theseus_ship::grammar::{detect_language, load_grammar};
use theseus_ship::reducer::Reducer;
use theseus_ship::shrink::run_shrink;

#[derive(Parser)]
#[command(
    name = "unfluff",
    version,
    about = "Syntax-guided program reduction (Perses algorithm)"
)]
struct Cli {
    /// Use the Python implementation instead of Rust
    #[arg(long, global = true)]
    legacy: bool,

    #[command(subcommand)]
    command: Option<Commands>,

    /// Source file to reduce (for default reduce command)
    input: Option<String>,
}

#[derive(Subcommand)]
enum Commands {
    /// Syntax-guided reduction (default)
    Reduce {
        /// Pytest test specification (e.g. test_file.py::test_name)
        #[arg(long, group = "test_mode")]
        test: Option<String>,

        /// Shell command (exit 0 = interesting, receives source on stdin)
        #[arg(long = "test-cmd", group = "test_mode")]
        test_cmd: Option<String>,

        /// Reduce to smallest syntactically valid program (no test needed)
        #[arg(long, group = "test_mode")]
        auto: bool,

        /// Reject any parse errors, including pre-existing ones
        #[arg(long, default_value_t = false)]
        strict: bool,

        /// Source file to reduce
        input: Option<String>,

        /// Override language detection
        #[arg(long)]
        lang: Option<String>,

        /// Output file path (default: overwrite input)
        #[arg(short, long)]
        output: Option<String>,

        /// Maximum reduction time (e.g. 30m, 1h)
        #[arg(long)]
        max_time: Option<String>,

        /// Maximum test invocations
        #[arg(long)]
        max_tests: Option<usize>,

        /// Parallel test workers
        #[arg(short, long, default_value_t = 1)]
        jobs: usize,

        /// Verbose output
        #[arg(short, long)]
        verbose: bool,

        /// Suppress output
        #[arg(short, long)]
        quiet: bool,
    },

    /// Analyze files and show reduction suggestions
    Check {
        /// Files or glob patterns to check
        files: Vec<String>,

        /// Apply safe fixes automatically
        #[arg(long)]
        fix: bool,

        /// Apply all fixes including unsafe ones
        #[arg(long = "unsafe-fixes")]
        unsafe_fixes: bool,

        /// Output format
        #[arg(long, value_enum, default_value = "text")]
        output_format: OutputFormat,

        /// Only check these rules (comma-separated)
        #[arg(long)]
        select: Option<String>,

        /// Ignore these rules (comma-separated)
        #[arg(long)]
        ignore: Option<String>,

        /// Override language detection for all files
        #[arg(long)]
        lang: Option<String>,

        /// Parallel file processing
        #[arg(short, long, default_value_t = 1)]
        jobs: usize,

        /// Suppress output
        #[arg(short, long)]
        quiet: bool,

        /// Verbose output
        #[arg(short, long)]
        verbose: bool,
    },

    /// Shrinkray-compatible reduction
    Shrink {
        /// Interestingness test command
        test: String,

        /// Source file to reduce
        file: String,

        /// Per-test timeout in seconds
        #[arg(long, default_value_t = 60.0)]
        timeout: f64,

        /// Backup file suffix
        #[arg(long, default_value = "")]
        backup: String,

        /// Number of parallel test workers
        #[arg(long, default_value_t = 1)]
        parallelism: usize,

        /// Override language detection
        #[arg(long)]
        lang: Option<String>,

        /// Output file path
        #[arg(short, long)]
        output: Option<String>,

        /// Maximum reduction time
        #[arg(long)]
        max_time: Option<String>,

        /// Maximum test invocations
        #[arg(long)]
        max_tests: Option<usize>,

        /// Verbose output
        #[arg(short, long)]
        verbose: bool,

        /// Suppress output
        #[arg(short, long)]
        quiet: bool,
    },
}

#[derive(clap::ValueEnum, Clone)]
enum OutputFormat {
    Text,
    Diff,
    Json,
}

fn parse_duration(s: &str) -> Result<f64, String> {
    let s = s.trim();
    if s.ends_with('s') {
        let val: f64 = s[..s.len() - 1]
            .parse()
            .map_err(|_| format!("Invalid duration: {} (use e.g. 30s, 5m, 1h)", s))?;
        Ok(val)
    } else if s.ends_with('m') {
        let val: f64 = s[..s.len() - 1]
            .parse()
            .map_err(|_| format!("Invalid duration: {} (use e.g. 30s, 5m, 1h)", s))?;
        Ok(val * 60.0)
    } else if s.ends_with('h') {
        let val: f64 = s[..s.len() - 1]
            .parse()
            .map_err(|_| format!("Invalid duration: {} (use e.g. 30s, 5m, 1h)", s))?;
        Ok(val * 3600.0)
    } else {
        Err(format!("Invalid duration: {} (use e.g. 30s, 5m, 1h)", s))
    }
}

fn expand_files(patterns: &[String]) -> Vec<PathBuf> {
    let mut files = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for pattern in patterns {
        let mut matches: Vec<PathBuf> = glob::glob(pattern)
            .map(|entries| entries.filter_map(|e| e.ok()).collect())
            .unwrap_or_default();
        if matches.is_empty() {
            matches.push(PathBuf::from(pattern));
        }
        for m in matches {
            if m.is_file() {
                let key = m.to_string_lossy().to_string();
                if seen.insert(key) {
                    files.push(m);
                }
            }
        }
    }
    files.sort();
    files
}

fn main() {
    let cli = Cli::parse();

    if cli.legacy {
        let mut cmd = process::Command::new("uv");
        cmd.arg("run").arg("theseus");
        for arg in env::args().skip(1) {
            if arg == "--legacy" {
                continue;
            }
            cmd.arg(arg);
        }
        let status = cmd.status().unwrap_or_else(|e| {
            eprintln!("Error: failed to run Python implementation: {}", e);
            process::exit(1);
        });
        process::exit(status.code().unwrap_or(1));
    }

    let exit_code = match cli.command {
        Some(Commands::Reduce { .. }) | None => {
            let (
                input,
                test,
                test_cmd,
                auto,
                strict,
                lang,
                output,
                max_time,
                max_tests,
                jobs,
                verbose,
                quiet,
            ) = match cli.command {
                Some(Commands::Reduce {
                    input,
                    test,
                    test_cmd,
                    auto,
                    strict,
                    lang,
                    output,
                    max_time,
                    max_tests,
                    jobs,
                    verbose,
                    quiet,
                }) => (
                    input, test, test_cmd, auto, strict, lang, output, max_time, max_tests, jobs,
                    verbose, quiet,
                ),
                _ => (
                    cli.input, None, None, false, false, None, None, None, None, 1, false, false,
                ),
            };

            let input = match input {
                Some(i) => i,
                None => {
                    eprintln!("Error: input file required (or use: unfluff reduce <file>)");
                    process::exit(1);
                }
            };

            if !auto && test.is_none() && test_cmd.is_none() {
                eprintln!("Error: --test, --test-cmd, or --auto required");
                process::exit(1);
            }

            let input_path = PathBuf::from(&input);
            if !input_path.exists() {
                eprintln!("Error: file not found: {}", input_path.display());
                process::exit(1);
            }

            let source = match fs::read(&input_path) {
                Ok(s) => s,
                Err(e) => {
                    eprintln!("Error reading {}: {}", input_path.display(), e);
                    process::exit(1);
                }
            };

            let lang_name = match lang {
                Some(l) => l,
                None => match detect_language(&input_path.to_string_lossy()) {
                    Ok(l) => l,
                    Err(e) => {
                        eprintln!("Error: {}", e);
                        process::exit(1);
                    }
                },
            };

            let grammar = match load_grammar(&lang_name) {
                Ok(g) => g,
                Err(e) => {
                    eprintln!("Error: {}", e);
                    process::exit(1);
                }
            };

            let output_path = output
                .map(PathBuf::from)
                .unwrap_or_else(|| input_path.clone());

            let max_time_secs = max_time.as_deref().map(parse_duration).transpose();
            let max_time_secs = match max_time_secs {
                Ok(v) => v,
                Err(e) => {
                    eprintln!("Error: {}", e);
                    process::exit(1);
                }
            };

            let mut reducer = Reducer::new(
                grammar,
                test,
                test_cmd,
                auto,
                max_time_secs,
                max_tests,
                jobs,
                verbose,
                quiet,
                strict,
            );

            let original_size = source.len();
            let result = reducer.reduce(&source);
            let reduced_size = result.source.len();

            if let Err(e) = fs::write(&output_path, &result.source) {
                eprintln!("Error writing {}: {}", output_path.display(), e);
                process::exit(1);
            }

            if !quiet {
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

        Some(Commands::Check {
            files,
            fix,
            unsafe_fixes,
            output_format,
            select,
            ignore,
            lang,
            jobs: _,
            verbose: _,
            quiet,
        }) => {
            use theseus_ship::checker::all_checks;
            use theseus_ship::diff::{apply_fixes, format_diff, format_json, format_text};
            use theseus_ship::rules::FixSafety;

            let file_patterns = if files.is_empty() {
                vec![".".to_string()]
            } else {
                files
            };

            let expanded = expand_files(&file_patterns);
            if expanded.is_empty() {
                eprintln!("Error: no files matched");
                process::exit(1);
            }

            let select_rules: Option<std::collections::HashSet<&str>> =
                select.as_deref().map(|s| s.split(',').collect());
            let ignore_rules: std::collections::HashSet<&str> = ignore
                .as_deref()
                .map(|s| s.split(',').collect())
                .unwrap_or_default();

            let checks = all_checks();
            let mut all_suggestions = Vec::new();

            for file_path in &expanded {
                let source = match fs::read(file_path) {
                    Ok(s) => s,
                    Err(_) => continue,
                };

                let file_str = file_path.to_string_lossy().to_string();
                let lang_name = match lang.as_deref() {
                    Some(l) => l.to_string(),
                    None => match detect_language(&file_str) {
                        Ok(l) => l,
                        Err(_) => continue,
                    },
                };

                let grammar = match load_grammar(&lang_name) {
                    Ok(g) => g,
                    Err(_) => continue,
                };

                for check_fn in &checks {
                    let suggestions = check_fn(&source, &grammar, &file_str);
                    for s in suggestions {
                        if let Some(ref sel) = select_rules {
                            if !sel.contains(s.rule.code) {
                                continue;
                            }
                        }
                        if ignore_rules.contains(s.rule.code) {
                            continue;
                        }
                        all_suggestions.push(s);
                    }
                }
            }

            if all_suggestions.is_empty() {
                if !quiet {
                    println!("All checks passed!");
                }
                process::exit(0);
            }

            match output_format {
                OutputFormat::Json => println!("{}", format_json(&all_suggestions)),
                OutputFormat::Diff => println!("{}", format_diff(&all_suggestions)),
                OutputFormat::Text => println!("{}", format_text(&all_suggestions)),
            }

            if fix || unsafe_fixes {
                let safety = if unsafe_fixes {
                    FixSafety::Unsafe
                } else {
                    FixSafety::Safe
                };
                let fixes = apply_fixes(&all_suggestions, safety);
                for (file_path, new_source) in &fixes {
                    if let Err(e) = fs::write(file_path, new_source) {
                        eprintln!("Error writing {}: {}", file_path, e);
                    }
                }
                if !quiet {
                    eprintln!(
                        "\nFixed {} file{}.",
                        fixes.len(),
                        if fixes.len() != 1 { "s" } else { "" }
                    );
                }
            }

            process::exit(1);
        }

        Some(Commands::Shrink {
            test,
            file,
            timeout,
            backup,
            parallelism,
            lang: _,
            output: _,
            max_time,
            max_tests,
            verbose,
            quiet,
        }) => {
            let max_time_secs = max_time.as_deref().map(parse_duration).transpose();
            let max_time_secs = match max_time_secs {
                Ok(v) => v,
                Err(e) => {
                    eprintln!("Error: {}", e);
                    process::exit(1);
                }
            };

            let backup_opt = if backup.is_empty() {
                None
            } else {
                Some(backup.as_str())
            };

            run_shrink(
                &test,
                &file,
                timeout,
                max_time_secs,
                max_tests,
                parallelism,
                backup_opt,
                verbose,
                quiet,
            )
        }
    };

    process::exit(exit_code);
}
