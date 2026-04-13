//! Contract test: present_recovery
//!
//! - `SurfaceLost` → Renderer recreates surface exactly once, continues.
//! - `DeviceLost` → Renderer marks itself fatal, OutputRuntime recreates.
//! - `Transient` → Skip frame, continue on next callback.
//!
//! Catches: treating all GPU errors identically (crash on screen blink vs
//! actual device loss) — a common mistake in wallpaper daemons.

use crate::mock_renderer::MockRenderer;
use std::sync::Arc;
use wpe_backend::frame::{CpuBuffer, DamageRegion, FrameOutput};
use wpe_render_core::error::PresentError;
use wpe_render_core::renderer::{PresentOutcome, Renderer, RendererStatus};

fn test_frame() -> FrameOutput {
    FrameOutput::Cpu {
        buffer: Arc::new(CpuBuffer::new_solid(100, 100, 0, 0, 0, 255)),
        damage: DamageRegion::Full,
    }
}

#[test]
fn surface_lost_recovery() {
    let mut renderer = MockRenderer::new();

    // First present — surface lost.
    renderer.next_present_error = Some(PresentError::SurfaceLost);
    let err = renderer.present(test_frame());
    assert!(matches!(err, Err(PresentError::SurfaceLost)));
    assert_eq!(renderer.status(), RendererStatus::SurfaceLost);

    // Simulate recovery: recreate surface once.
    renderer.recreate_surface();
    assert_eq!(renderer.status(), RendererStatus::Ready);
    assert_eq!(renderer.surface_recreate_count, 1);

    // Next present should succeed.
    let result = renderer.present(test_frame());
    assert!(matches!(result, Ok(PresentOutcome::Presented)));
}

#[test]
fn device_lost_is_fatal() {
    let mut renderer = MockRenderer::new();

    renderer.next_present_error = Some(PresentError::DeviceLost);
    let err = renderer.present(test_frame());
    assert!(matches!(err, Err(PresentError::DeviceLost)));
    assert_eq!(renderer.status(), RendererStatus::DeviceLost);

    // DeviceLost means OutputRuntime must recreate entirely.
    // Renderer should not attempt recovery itself.
}

#[test]
fn transient_error_skips_frame() {
    let mut renderer = MockRenderer::new();

    // Successful present first.
    let r = renderer.present(test_frame());
    assert!(matches!(r, Ok(PresentOutcome::Presented)));
    assert_eq!(renderer.present_count, 1);

    // Transient error — skip this frame.
    renderer.next_present_error = Some(PresentError::Transient);
    let err = renderer.present(test_frame());
    assert!(matches!(err, Err(PresentError::Transient)));

    // Renderer is still ready.
    assert_eq!(renderer.status(), RendererStatus::Ready);

    // Next present succeeds.
    let r = renderer.present(test_frame());
    assert!(matches!(r, Ok(PresentOutcome::Presented)));
    assert_eq!(renderer.present_count, 2);
}

#[test]
fn unchanged_frame_is_skipped() {
    let mut renderer = MockRenderer::new();

    let result = renderer.present(FrameOutput::Unchanged);
    assert!(matches!(result, Ok(PresentOutcome::Skipped)));
    assert_eq!(renderer.present_count, 0, "Unchanged should not count as presented");
}
