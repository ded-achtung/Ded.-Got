use crate::fallback::IgnoredItem;
use crate::warning::CompatWarning;
use std::path::PathBuf;

#[derive(Debug)]
pub struct LoadReport {
    pub status: LoadStatus,
    pub warnings: Vec<CompatWarning>,
    pub ignored: Vec<IgnoredItem>,
    pub asset_stats: AssetStats,
}

#[derive(Debug)]
pub enum LoadStatus {
    Ok,
    Partial { severity: PartialSeverity },
    Failed(LoadError),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PartialSeverity {
    Cosmetic,
    Visible,
    Major,
}

#[derive(Debug)]
pub enum LoadError {
    ManifestInvalid(String),
    AssetMissing(PathBuf),
    FormatUnsupported {
        found: String,
        supported: Vec<String>,
    },
    NegotiationFailed(String),
    Io(std::io::Error),
}

#[derive(Debug, Default)]
pub struct AssetStats {
    pub total_bytes: u64,
    pub image_count: u32,
    // TODO 0.2: shader_count (with shader backend)
    // TODO 0.1-stretch/0.2: video_frame_stats (with video backend)
}
