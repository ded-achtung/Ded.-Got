#[derive(Debug, Clone)]
pub struct CompatWarning {
    pub code: CompatWarningCode,
    pub context: String,
    pub suggestion: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompatWarningCode {
    /// W001 — source image smaller than output resolution.
    ImageSmallerThanOutput,
    /// W002 — EXIF metadata broken or unreadable.
    ImageExifBroken,
    // TODO 0.1-stretch: W010 VideoResolutionHuge (only if video enters 0.1)
    /// W023 — wp_fractional_scale_v1 protocol unavailable.
    FractionalScaleUnavailable,
    /// W024 — wp_viewporter missing while fractional-scale present.
    /// Fractional scaling degrades to integer scaling.
    ViewporterUnavailable,
    /// W025 — wp_content_type_v1 unavailable, no compositor hints.
    ContentTypeUnavailable,
    /// W040 — ext_foreign_toplevel_list_v1 unavailable, no fullscreen detection.
    ForeignToplevelUnavailable,
    // TODO 0.2: W020 ShaderUndefinedUniform (with shader backend)
    // TODO 0.2: W041 IdleNotifyUnavailable (with pause-on-idle)
}
