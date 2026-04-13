/// Opaque GPU texture handle. Internals are Renderer implementation detail.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct TextureHandle(pub(crate) u64);

/// Opaque GPU buffer handle.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct BufferHandle(pub(crate) u64);

/// Opaque render pipeline handle.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct PipelineHandle(pub(crate) u64);

/// Opaque render target handle.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct TargetHandle(pub(crate) u64);
