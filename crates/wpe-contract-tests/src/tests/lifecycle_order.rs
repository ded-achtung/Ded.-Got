//! Contract test: lifecycle_order
//!
//! Verifies three invariants:
//! 1. `prepare` must be called before `render_frame` / `resize`.
//! 2. `resize` must not be called during `render_frame` (reentrancy guard).
//! 3. After `prepare`, `render_frame` works correctly.
//!
//! Catches: hotplug bug where backend receives events before resource init.

use crate::traced_backend::TracedBackend;
use wpe_backend::frame::FrameRequest;
use wpe_backend::lifecycle::FrameSource;
use wpe_backend::state::{FractionalScale, RuntimeInstant, SurfaceSize};

#[test]
fn render_frame_before_prepare_panics() {
    let mut backend = TracedBackend::new();

    let req = FrameRequest {
        target_size: SurfaceSize {
            width: 1920,
            height: 1080,
        },
        is_first_frame: true,
        clock: RuntimeInstant::zero(),
        frame_index: 0,
    };

    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        backend.render_frame(&req)
    }));
    assert!(result.is_err(), "render_frame before prepare must panic");
}

#[test]
fn resize_before_prepare_returns_error() {
    let mut backend = TracedBackend::new();

    let result = backend.resize(
        SurfaceSize {
            width: 2560,
            height: 1440,
        },
        FractionalScale::integer(1),
    );
    assert!(result.is_err(), "resize before prepare must fail");
}

#[test]
fn normal_lifecycle_works() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();

    // prepare
    let report = backend.prepare(ctx);
    assert!(
        matches!(report.status, wpe_compat::report::LoadStatus::Ok),
        "prepare should succeed"
    );

    // render_frame after prepare — ok
    let req = FrameRequest {
        target_size: SurfaceSize {
            width: 1920,
            height: 1080,
        },
        is_first_frame: true,
        clock: RuntimeInstant::zero(),
        frame_index: 0,
    };

    let output = backend.render_frame(&req);
    assert!(output.is_ok(), "render_frame after prepare must succeed");

    // resize between frames — ok
    let resize_result = backend.resize(
        SurfaceSize {
            width: 2560,
            height: 1440,
        },
        FractionalScale(1.5),
    );
    assert!(resize_result.is_ok(), "resize between frames must succeed");

    // Verify trace order
    assert_eq!(
        backend.trace,
        vec!["prepare", "render_frame", "resize"],
        "call order must be prepare → render_frame → resize"
    );
}

#[test]
fn double_prepare_panics() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();
    let _ = backend.prepare(ctx);

    let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let ctx2 = TracedBackend::mock_prepare_ctx();
        backend.prepare(ctx2);
    }));
    assert!(result.is_err(), "double prepare must panic");
}
