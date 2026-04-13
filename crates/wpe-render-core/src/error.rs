use std::fmt;

/// Errors during frame presentation.
#[derive(Debug)]
pub enum PresentError {
    /// Surface invalidated — recreate wgpu surface, retry.
    SurfaceLost,
    /// GPU device lost — recreate entire OutputRuntime.
    DeviceLost,
    /// Transient error — skip this frame, retry next.
    Transient,
}

impl fmt::Display for PresentError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::SurfaceLost => write!(f, "surface lost"),
            Self::DeviceLost => write!(f, "device lost"),
            Self::Transient => write!(f, "transient error"),
        }
    }
}

impl std::error::Error for PresentError {}
