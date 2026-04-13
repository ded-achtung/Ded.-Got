use wpe_backend::BackendCapabilities;

/// Result of `Renderer::negotiate` — can this renderer work with this backend?
#[derive(Debug)]
pub enum NegotiationResult {
    /// Full compatibility.
    Compatible,
    /// Works with limitations.
    CompatibleWithLimitations(Vec<NegotiationNote>),
    /// Cannot work together.
    Incompatible(NegotiationError),
}

#[derive(Debug, Clone)]
pub struct NegotiationNote {
    pub message: String,
}

#[derive(Debug, Clone)]
pub struct NegotiationError {
    pub reason: String,
    pub renderer_supports: String,
    pub backend_requires: String,
}

/// Check compatibility between renderer and backend capabilities.
/// Pure function — no side effects.
pub fn check_compatibility(
    _renderer_format: SurfaceFormat,
    caps: &BackendCapabilities,
) -> NegotiationResult {
    use wpe_backend::FrameSourceKind;

    match caps.source_kind {
        FrameSourceKind::CpuRgba | FrameSourceKind::Static => NegotiationResult::Compatible,
        FrameSourceKind::DeviceEncoded => {
            // DeviceEncoded requires renderer to provide a target.
            // For 0.1 image backend this path is unused.
            NegotiationResult::CompatibleWithLimitations(vec![NegotiationNote {
                message: "DeviceEncoded requires device target support".into(),
            }])
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SurfaceFormat {
    Bgra8Unorm,
    Rgba8Unorm,
}
