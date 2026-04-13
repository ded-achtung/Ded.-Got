use std::time::Duration;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SurfaceSize {
    pub width: u32,
    pub height: u32,
}

#[derive(Clone, Copy, Debug, PartialEq, PartialOrd)]
pub struct FractionalScale(pub f64);

impl FractionalScale {
    pub fn integer(scale: u32) -> Self {
        Self(f64::from(scale))
    }
}

/// Monotonic time since daemon start. Paused when daemon is paused.
/// Backends must use this instead of `std::time::Instant::now()`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct RuntimeInstant(pub u64); // nanoseconds

impl RuntimeInstant {
    pub fn zero() -> Self {
        Self(0)
    }

    pub fn from_nanos(ns: u64) -> Self {
        Self(ns)
    }

    pub fn as_nanos(self) -> u64 {
        self.0
    }
}

#[derive(Clone, Copy, Debug)]
pub struct FrameDelta(pub Duration);

impl FrameDelta {
    pub fn from_millis(ms: u64) -> Self {
        Self(Duration::from_millis(ms))
    }

    pub fn as_duration(self) -> Duration {
        self.0
    }
}

#[derive(Clone, Debug)]
pub struct OutputGeometry {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
    pub scale: FractionalScale,
}
