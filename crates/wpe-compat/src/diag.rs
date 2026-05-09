use crate::support::{ImageFormat, SupportLevel, SupportMatrix};
use crate::warning::{CompatWarning, CompatWarningCode};

#[derive(Debug, Clone)]
pub struct DiagWarning {
    pub code: CompatWarningCode,
    pub context: String,
    pub suggestion: Option<String>,
}

#[derive(Debug, Clone)]
pub struct DiagReport {
    /// Unix timestamp in milliseconds.
    pub timestamp_ms: u64,
    /// Number of outputs detected by runtime (if known).
    pub outputs_detected: Option<u32>,
    /// Number of outputs currently active/presenting (if known).
    pub outputs_active: Option<u32>,
    /// Current FPS measurement (if known).
    pub fps: Option<f32>,
    /// Current RSS in MiB (if known).
    pub memory_mib: Option<u64>,
    /// Image support snapshot from `SupportMatrix`.
    pub image_support: Vec<(ImageFormat, SupportLevel)>,
    /// Compatibility warnings visible to user.
    pub warnings: Vec<DiagWarning>,
}

impl DiagReport {
    pub fn from_warnings(timestamp_ms: u64, warnings: &[CompatWarning]) -> Self {
        let image_support = SupportMatrix::current()
            .image_formats
            .iter()
            .map(|(fmt, level)| (*fmt, *level))
            .collect();

        let warnings = warnings
            .iter()
            .map(|w| DiagWarning {
                code: w.code,
                context: w.context.clone(),
                suggestion: w.suggestion.clone(),
            })
            .collect();

        Self {
            timestamp_ms,
            outputs_detected: None,
            outputs_active: None,
            fps: None,
            memory_mib: None,
            image_support,
            warnings,
        }
    }

    /// Human-readable diagnostic block for `wpe diag` CLI skeleton.
    pub fn to_text(&self) -> String {
        let mut out = String::new();
        out.push_str("wpe diag\n");
        out.push_str(&format!("timestamp_ms: {}\n", self.timestamp_ms));
        out.push_str(&format!(
            "outputs: detected={:?} active={:?}\n",
            self.outputs_detected, self.outputs_active
        ));
        out.push_str(&format!(
            "metrics: fps={:?} memory_mib={:?}\n",
            self.fps, self.memory_mib
        ));
        out.push_str("image_support:\n");
        for (fmt, level) in &self.image_support {
            out.push_str(&format!("  - {:?}: {:?}\n", fmt, level));
        }
        out.push_str(&format!("warnings: {}\n", self.warnings.len()));
        for w in &self.warnings {
            out.push_str(&format!(
                "  - {}: {}",
                warning_code_label(w.code),
                w.context
            ));
            if let Some(s) = &w.suggestion {
                out.push_str(&format!(" (suggestion: {})", s));
            }
            out.push('\n');
        }
        out
    }
}

fn warning_code_label(code: CompatWarningCode) -> &'static str {
    match code {
        CompatWarningCode::ImageSmallerThanOutput => "W001",
        CompatWarningCode::ImageExifBroken => "W002",
        CompatWarningCode::FractionalScaleUnavailable => "W023",
        CompatWarningCode::ViewporterUnavailable => "W024",
        CompatWarningCode::ContentTypeUnavailable => "W025",
        CompatWarningCode::ForeignToplevelUnavailable => "W040",
    }
}

#[cfg(test)]
mod tests {
    use super::DiagReport;
    use crate::warning::{CompatWarning, CompatWarningCode};

    #[test]
    fn diag_report_includes_warning_codes_and_support_snapshot() {
        let warnings = vec![
            CompatWarning {
                code: CompatWarningCode::ViewporterUnavailable,
                context: "wp_viewporter missing".to_string(),
                suggestion: Some("use integer scaling fallback".to_string()),
            },
            CompatWarning {
                code: CompatWarningCode::ForeignToplevelUnavailable,
                context: "no fullscreen detection".to_string(),
                suggestion: None,
            },
        ];

        let report = DiagReport::from_warnings(1234, &warnings);
        let text = report.to_text();

        assert!(text.contains("timestamp_ms: 1234"));
        assert!(text.contains("W024"));
        assert!(text.contains("W040"));
        assert!(text.contains("image_support:"));
        assert!(
            report.image_support.len() >= 3,
            "must include support snapshot from SupportMatrix"
        );
    }
}
