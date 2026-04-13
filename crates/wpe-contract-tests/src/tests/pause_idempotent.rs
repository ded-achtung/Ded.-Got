//! Contract test: pause_idempotent
//!
//! Double `pause` — noop. Double `resume` — noop.
//! `pause` after `pause` without `resume` does not crash.
//!
//! Catches: crash on burst events from ext-foreign-toplevel-list-v1
//! where compositor sends two fullscreen events in a row.

use crate::traced_backend::TracedBackend;
use wpe_backend::error::BackendStatus;
use wpe_backend::lifecycle::FrameSource;

#[test]
fn double_pause_is_noop() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();
    let _ = backend.prepare(ctx);

    backend.pause();
    assert_eq!(backend.status(), BackendStatus::Paused);

    // Second pause — must not crash, status stays Paused.
    backend.pause();
    assert_eq!(backend.status(), BackendStatus::Paused);
}

#[test]
fn double_resume_is_noop() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();
    let _ = backend.prepare(ctx);

    backend.pause();
    backend.resume();
    assert_eq!(backend.status(), BackendStatus::Ready);

    // Second resume — must not crash, status stays Ready.
    backend.resume();
    assert_eq!(backend.status(), BackendStatus::Ready);
}

#[test]
fn pause_resume_cycle() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();
    let _ = backend.prepare(ctx);

    for _ in 0..10 {
        backend.pause();
        assert_eq!(backend.status(), BackendStatus::Paused);
        backend.resume();
        assert_eq!(backend.status(), BackendStatus::Ready);
    }
}

#[test]
fn resume_without_pause_is_noop() {
    let mut backend = TracedBackend::new();
    let ctx = TracedBackend::mock_prepare_ctx();
    let _ = backend.prepare(ctx);

    // resume without prior pause — should not crash or change status
    backend.resume();
    assert_eq!(backend.status(), BackendStatus::Ready);
}
