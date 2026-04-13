use std::path::Path;
use std::sync::Arc;
use wpe_backend::caps::{
    BackendCapabilities, ContentTypeHint, FrameSourceKind, PauseSemantics, ResizePolicy,
};
use wpe_backend::error::{BackendError, BackendStatus};
use wpe_backend::frame::{CpuBuffer, DamageRegion, FrameOutput, FrameRequest};
use wpe_backend::lifecycle::{FrameSource, PrepareCtx};
use wpe_backend::state::{FractionalScale, SurfaceSize};
use wpe_compat::report::{AssetStats, LoadReport, LoadStatus};

/// Lifecycle phase tracking for contract enforcement.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Phase {
    Created,
    Prepared,
    Rendering,
    Paused,
    Failed,
}

/// Simple FrameSource implementation that records call order for contract tests.
pub struct TracedBackend {
    phase: Phase,
    /// Whether `render_frame` is currently executing (reentrancy guard).
    in_render: bool,
    /// Number of frames rendered.
    pub frames_rendered: u32,
    /// Whether the last render_frame returned Unchanged.
    first_frame_done: bool,
    /// Call trace for debugging.
    pub trace: Vec<&'static str>,
    /// Surface dimensions after last resize.
    size: SurfaceSize,
}

impl TracedBackend {
    pub fn new() -> Self {
        Self {
            phase: Phase::Created,
            in_render: false,
            frames_rendered: 0,
            first_frame_done: false,
            trace: Vec::new(),
            size: SurfaceSize {
                width: 1920,
                height: 1080,
            },
        }
    }

    pub fn mock_prepare_ctx() -> PrepareCtx<'static> {
        PrepareCtx {
            asset_path: Path::new("/tmp/test.png"),
            target_size: SurfaceSize {
                width: 1920,
                height: 1080,
            },
            scale: FractionalScale::integer(1),
        }
    }
}

impl FrameSource for TracedBackend {
    fn capabilities(&self) -> BackendCapabilities {
        BackendCapabilities {
            source_kind: FrameSourceKind::Static,
            resize: ResizePolicy::Immediate,
            pause_semantics: PauseSemantics::Freeze,
            content_type_hint: ContentTypeHint::Photo,
        }
    }

    fn prepare(&mut self, ctx: PrepareCtx<'_>) -> LoadReport {
        self.trace.push("prepare");

        if self.phase != Phase::Created {
            panic!("prepare called in phase {:?}, expected Created", self.phase);
        }

        self.phase = Phase::Prepared;
        self.size = ctx.target_size;

        LoadReport {
            status: LoadStatus::Ok,
            warnings: Vec::new(),
            ignored: Vec::new(),
            asset_stats: AssetStats {
                total_bytes: 1024,
                image_count: 1,
            },
        }
    }

    fn resize(
        &mut self,
        size: SurfaceSize,
        _scale: FractionalScale,
    ) -> Result<(), BackendError> {
        self.trace.push("resize");

        if self.in_render {
            panic!("resize called during render_frame — reentrancy violation");
        }

        match self.phase {
            Phase::Created => {
                return Err(BackendError::InvalidState("resize before prepare"));
            }
            Phase::Failed => {
                return Err(BackendError::InvalidState("resize after failure"));
            }
            Phase::Prepared | Phase::Rendering | Phase::Paused => {}
        }

        self.size = size;
        Ok(())
    }

    fn render_frame(&mut self, req: &FrameRequest) -> Result<FrameOutput, BackendError> {
        self.trace.push("render_frame");

        match self.phase {
            Phase::Created => {
                panic!("render_frame called before prepare");
            }
            Phase::Failed => {
                return Err(BackendError::InvalidState("render_frame after failure"));
            }
            Phase::Paused => {
                return Err(BackendError::InvalidState("render_frame while paused"));
            }
            Phase::Prepared | Phase::Rendering => {}
        }

        self.in_render = true;
        self.phase = Phase::Rendering;

        let output = if req.is_first_frame || !self.first_frame_done {
            self.first_frame_done = true;
            self.frames_rendered += 1;
            FrameOutput::Cpu {
                buffer: Arc::new(CpuBuffer::new_solid(
                    self.size.width,
                    self.size.height,
                    38, 51, 77, 255, // dark blue, like prototype
                )),
                damage: DamageRegion::Full,
            }
        } else {
            // Static image — nothing changed after first frame.
            FrameOutput::Unchanged
        };

        self.in_render = false;
        Ok(output)
    }

    fn pause(&mut self) {
        self.trace.push("pause");
        // Idempotent — double pause is noop.
        if self.phase != Phase::Failed {
            self.phase = Phase::Paused;
        }
    }

    fn resume(&mut self) {
        self.trace.push("resume");
        // Idempotent — double resume is noop.
        if self.phase == Phase::Paused {
            self.phase = Phase::Rendering;
        }
    }

    fn status(&self) -> BackendStatus {
        match self.phase {
            Phase::Created => BackendStatus::Ready,
            Phase::Prepared | Phase::Rendering => BackendStatus::Ready,
            Phase::Paused => BackendStatus::Paused,
            Phase::Failed => BackendStatus::Failed,
        }
    }
}
