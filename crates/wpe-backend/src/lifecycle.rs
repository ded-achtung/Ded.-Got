use crate::caps::BackendCapabilities;
use crate::error::{BackendError, BackendStatus};
use crate::frame::{FrameOutput, FrameRequest};
use crate::state::{FractionalScale, SurfaceSize};
use wpe_compat::report::LoadReport;

/// Context for `FrameSource::prepare`.
pub struct PrepareCtx<'a> {
    pub asset_path: &'a std::path::Path,
    pub target_size: SurfaceSize,
    pub scale: FractionalScale,
}

/// Single contract between Backend and Renderer.
///
/// Updated after prototype: uses `render_frame` (single entry point)
/// instead of the old `update` + `produce` pair. This matches Wayland's
/// frame-callback-driven rendering model:
///
/// 1. Compositor sends `wl_callback::done` when ready for next frame.
/// 2. OutputRuntime calls `render_frame` on the backend.
/// 3. Backend returns `FrameOutput` (CPU buffer, Unchanged, etc.).
/// 4. Renderer presents the frame and requests next callback.
///
/// For static content (image), `render_frame` returns `Unchanged` after
/// the first frame. For animated content (video, shader), it returns
/// new frames on each callback.
pub trait FrameSource: Send {
    /// Capabilities of this backend. Pure, callable at any time.
    fn capabilities(&self) -> BackendCapabilities;

    /// Load and prepare assets. Called exactly once before any other
    /// method (except `capabilities`). May be slow (file I/O, decode).
    fn prepare(&mut self, ctx: PrepareCtx<'_>) -> LoadReport;

    /// Handle surface resize. Must not be called during `render_frame`.
    fn resize(
        &mut self,
        size: SurfaceSize,
        scale: FractionalScale,
    ) -> Result<(), BackendError>;

    /// Produce a frame. Single entry point, driven by compositor
    /// frame callback. Returns `FrameOutput::Unchanged` when nothing
    /// changed (static image after first frame).
    fn render_frame(&mut self, req: &FrameRequest) -> Result<FrameOutput, BackendError>;

    /// Pause rendering. Idempotent — double pause is noop.
    fn pause(&mut self);

    /// Resume rendering. Idempotent — double resume is noop.
    fn resume(&mut self);

    /// Current status. No side effects.
    fn status(&self) -> BackendStatus;
}
