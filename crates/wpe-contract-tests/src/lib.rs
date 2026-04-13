//! Contract tests for wpe-rs.
//!
//! These tests verify invariants that, if violated, cause real bugs in
//! wallpaper daemons. Each test catches a specific class of failures
//! observed in similar projects (swww, hyprpaper, mpvpaper).
//!
//! 5 contract tests:
//! - lifecycle_order: prepare before render_frame, resize not during render
//! - pause_idempotent: double pause/resume is noop
//! - present_recovery: SurfaceLost vs DeviceLost recovery paths
//! - no_gpu_in_backend: wpe-backend must not import wgpu
//! - frame_output_invariants: FrameOutput type invariants

#[cfg(test)]
mod mock_renderer;
#[cfg(test)]
mod traced_backend;

#[cfg(test)]
mod tests;
