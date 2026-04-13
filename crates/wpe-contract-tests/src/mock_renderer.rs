use wpe_backend::caps::BackendCapabilities;
use wpe_backend::frame::FrameOutput;
use wpe_backend::state::SurfaceSize;
use wpe_render_core::error::PresentError;
use wpe_render_core::negotiation::{NegotiationResult, SurfaceFormat};
use wpe_render_core::renderer::{PresentOutcome, Renderer, RendererStatus};

/// Mock Renderer that records calls and can be configured to return errors.
pub struct MockRenderer {
    pub present_count: u32,
    pub status: RendererStatus,
    /// If set, next `present` will return this error.
    pub next_present_error: Option<PresentError>,
    /// Count of surface recreations after SurfaceLost.
    pub surface_recreate_count: u32,
}

impl MockRenderer {
    pub fn new() -> Self {
        Self {
            present_count: 0,
            status: RendererStatus::Ready,
            next_present_error: None,
            surface_recreate_count: 0,
        }
    }

    /// Simulate surface recreation after SurfaceLost.
    pub fn recreate_surface(&mut self) {
        self.surface_recreate_count += 1;
        self.status = RendererStatus::Ready;
    }
}

impl Renderer for MockRenderer {
    fn surface_format(&self) -> SurfaceFormat {
        SurfaceFormat::Bgra8Unorm
    }

    fn surface_size(&self) -> SurfaceSize {
        SurfaceSize {
            width: 1920,
            height: 1080,
        }
    }

    fn negotiate(&self, _caps: &BackendCapabilities) -> NegotiationResult {
        NegotiationResult::Compatible
    }

    fn present(&mut self, frame: FrameOutput) -> Result<PresentOutcome, PresentError> {
        if let Some(err) = self.next_present_error.take() {
            match &err {
                PresentError::SurfaceLost => {
                    self.status = RendererStatus::SurfaceLost;
                }
                PresentError::DeviceLost => {
                    self.status = RendererStatus::DeviceLost;
                }
                PresentError::Transient => {}
            }
            return Err(err);
        }

        let outcome = match &frame {
            FrameOutput::Unchanged | FrameOutput::SkippedDegraded(_) => PresentOutcome::Skipped,
            FrameOutput::Cpu { .. } | FrameOutput::DeviceEncoded => {
                self.present_count += 1;
                PresentOutcome::Presented
            }
        };

        Ok(outcome)
    }

    fn status(&self) -> RendererStatus {
        self.status
    }
}
