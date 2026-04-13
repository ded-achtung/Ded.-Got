use crate::error::PresentError;
use crate::negotiation::{NegotiationResult, SurfaceFormat};
use wpe_backend::caps::BackendCapabilities;
use wpe_backend::frame::FrameOutput;
use wpe_backend::state::SurfaceSize;

/// Outcome of a successful `present` call.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PresentOutcome {
    /// Frame was presented to the surface.
    Presented,
    /// Frame was skipped (e.g. FrameOutput::Unchanged).
    Skipped,
}

/// Current health of the renderer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RendererStatus {
    Ready,
    SurfaceLost,
    DeviceLost,
}

/// Contract for presenting frames to a Wayland surface.
///
/// Renderer owns the GPU device and surface. It takes `FrameOutput`
/// from the backend and presents it. Backend never touches GPU
/// resources directly (P1, P2 from RUNTIME.md).
pub trait Renderer {
    /// Pixel format of the surface.
    fn surface_format(&self) -> SurfaceFormat;

    /// Current surface dimensions.
    fn surface_size(&self) -> SurfaceSize;

    /// Check compatibility with backend before `prepare`.
    /// Pure function — no side effects.
    fn negotiate(&self, caps: &BackendCapabilities) -> NegotiationResult;

    /// Present a frame to the surface.
    ///
    /// Recovery contract:
    /// - `SurfaceLost` → Renderer recreates surface exactly once, then retries.
    /// - `DeviceLost` → Renderer marks itself fatal, OutputRuntime recreates.
    /// - `Transient` → Skip frame, retry on next callback.
    fn present(&mut self, frame: FrameOutput) -> Result<PresentOutcome, PresentError>;

    /// Current health status.
    fn status(&self) -> RendererStatus;
}
