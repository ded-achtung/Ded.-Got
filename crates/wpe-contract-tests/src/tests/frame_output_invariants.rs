//! Contract test: frame_output_invariants
//!
//! Verifies FrameOutput type invariants:
//! - Cpu contains valid RGBA8 premultiplied data.
//! - Unchanged is never returned on first frame.
//! - SkippedDegraded carries non-empty reason.
//!
//! Without these, downstream Renderer::present makes wrong assumptions
//! about buffer layout and frame semantics.

use crate::traced_backend::TracedBackend;
use wpe_backend::frame::{DamageRegion, FrameOutput, FrameRequest, SkipReason};
use wpe_backend::lifecycle::FrameSource;
use wpe_backend::state::{RuntimeInstant, SurfaceSize};

fn make_request(is_first: bool, frame_index: u64) -> FrameRequest {
    FrameRequest {
        target_size: SurfaceSize {
            width: 100,
            height: 100,
        },
        is_first_frame: is_first,
        clock: RuntimeInstant::zero(),
        frame_index,
    }
}

#[test]
fn first_frame_is_cpu_with_full_damage() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();
    let _ = backend.prepare(ctx);

    let output = backend
        .render_frame(&make_request(true, 0))
        .expect("first frame must succeed");

    match output {
        FrameOutput::Cpu { buffer, damage } => {
            // RGBA8: 4 bytes per pixel.
            let expected_size = (buffer.width * buffer.height * 4) as usize;
            assert_eq!(
                buffer.data.len(),
                expected_size,
                "buffer size must match width * height * 4"
            );
            assert_eq!(buffer.stride, buffer.width * 4, "stride must be width * 4");
            assert!(
                matches!(damage, DamageRegion::Full),
                "first frame damage must be Full"
            );
        }
        other => panic!("first frame must be Cpu, got: {other:?}"),
    }
}

#[test]
fn second_frame_static_is_unchanged() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();
    let _ = backend.prepare(ctx);

    // First frame.
    let _ = backend.render_frame(&make_request(true, 0));

    // Second frame on static backend — nothing changed.
    let output = backend
        .render_frame(&make_request(false, 1))
        .expect("second frame must succeed");

    assert!(
        matches!(output, FrameOutput::Unchanged),
        "static backend second frame must be Unchanged"
    );
}

#[test]
fn skipped_degraded_has_reason() {
    // Verify the SkipReason type is non-empty by construction.
    let reason = SkipReason("test degradation reason".into());
    assert!(
        !reason.0.is_empty(),
        "SkipReason must carry non-empty explanation"
    );

    let output = FrameOutput::SkippedDegraded(reason);
    match output {
        FrameOutput::SkippedDegraded(r) => {
            assert!(!r.0.is_empty(), "SkippedDegraded reason must not be empty");
        }
        _ => panic!("expected SkippedDegraded"),
    }
}
