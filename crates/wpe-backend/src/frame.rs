use crate::state::{RuntimeInstant, SurfaceSize};
use std::sync::Arc;

/// Request passed to `FrameSource::render_frame`.
/// Driven by Wayland frame callback — compositor decides when to request.
pub struct FrameRequest {
    pub target_size: SurfaceSize,
    pub is_first_frame: bool,
    pub clock: RuntimeInstant,
    pub frame_index: u64,
}

/// Result of `FrameSource::render_frame`.
#[derive(Debug)]
pub enum FrameOutput {
    /// CPU-side RGBA8 buffer, premultiplied alpha, row-major.
    Cpu {
        buffer: Arc<CpuBuffer>,
        damage: DamageRegion,
    },
    /// Backend rendered directly into device target.
    DeviceEncoded,
    /// Nothing changed since last frame — Renderer skips present.
    /// Must NOT be returned on the first frame.
    Unchanged,
    /// Frame skipped due to degraded state.
    SkippedDegraded(SkipReason),
}

#[derive(Debug, Clone)]
pub struct CpuBuffer {
    pub data: Vec<u8>, // RGBA8, premultiplied alpha
    pub width: u32,
    pub height: u32,
    pub stride: u32, // bytes per row (width * 4 for RGBA8)
}

impl CpuBuffer {
    pub fn new_solid(width: u32, height: u32, r: u8, g: u8, b: u8, a: u8) -> Self {
        let stride = width * 4;
        let mut data = Vec::with_capacity((stride * height) as usize);
        for _ in 0..width * height {
            data.extend_from_slice(&[r, g, b, a]);
        }
        Self {
            data,
            width,
            height,
            stride,
        }
    }
}

#[derive(Debug, Clone)]
pub enum DamageRegion {
    /// Entire surface changed — full repaint.
    Full,
    /// Specific rectangles changed.
    Partial(Vec<DamageRect>),
    /// Nothing changed — compositor can skip compositing this surface.
    Empty,
}

#[derive(Debug, Clone)]
pub struct DamageRect {
    pub x: i32,
    pub y: i32,
    pub width: i32,
    pub height: i32,
}

#[derive(Debug, Clone)]
pub struct SkipReason(pub String);
