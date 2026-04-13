//! Contract test: no_gpu_in_backend
//!
//! wpe-backend must not import `wgpu`. This is enforced by:
//! 1. Cargo.toml — wpe-backend has no wgpu dependency.
//! 2. forbidden-imports.sh — grep-based CI check.
//! 3. This test — compile-time smoke check that the guard is in place.
//!
//! The test verifies that TracedBackend (our mock FrameSource) compiles
//! and runs without any GPU types, confirming the architectural boundary
//! that backends operate on CPU-level abstractions only.

use crate::traced_backend::TracedBackend;
use wpe_backend::caps::FrameSourceKind;
use wpe_backend::frame::{FrameOutput, FrameRequest};
use wpe_backend::lifecycle::FrameSource;
use wpe_backend::state::{RuntimeInstant, SurfaceSize};

#[test]
fn backend_produces_cpu_output_without_gpu() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();
    let _ = backend.prepare(ctx);

    // Backend capabilities declare CPU-level source.
    let caps = backend.capabilities();
    assert!(
        matches!(caps.source_kind, FrameSourceKind::Static | FrameSourceKind::CpuRgba),
        "backend source_kind must be CPU-level, not DeviceEncoded"
    );

    // render_frame returns CPU buffer, not device-encoded.
    let req = FrameRequest {
        target_size: SurfaceSize {
            width: 100,
            height: 100,
        },
        is_first_frame: true,
        clock: RuntimeInstant::zero(),
        frame_index: 0,
    };

    let output = backend.render_frame(&req).expect("render must succeed");
    assert!(
        matches!(output, FrameOutput::Cpu { .. }),
        "first frame must be Cpu, got: {output:?}"
    );
}
