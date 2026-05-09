use std::time::{SystemTime, UNIX_EPOCH};
use wpe_compat::diag::DiagReport;
use wpe_compat::warning::{CompatWarning, CompatWarningCode};

fn main() {
    let mut args = std::env::args().skip(1);
    match args.next().as_deref() {
        Some("diag") => run_diag(),
        _ => print_usage(),
    }
}

fn run_diag() {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0);

    // Placeholder warnings until runtime probing is wired.
    let warnings = vec![CompatWarning {
        code: CompatWarningCode::ForeignToplevelUnavailable,
        context: "fullscreen pause protocol not probed yet (cli skeleton)".to_string(),
        suggestion: Some("wire runtime protocol probing in wpe-wayland".to_string()),
    }];

    let report = DiagReport::from_warnings(now, &warnings);
    println!("{}", report.to_text());
}

fn print_usage() {
    eprintln!("usage: wpe-cli diag");
}
