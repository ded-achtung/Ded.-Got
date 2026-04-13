#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FrameSourceKind {
    /// CPU buffer RGBA8. Always works.
    CpuRgba,
    /// Backend already rendered into a device-provided target.
    DeviceEncoded,
    /// Static source. Renderer may cache the texture.
    Static,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ResizePolicy {
    /// Backend handles resize immediately in `resize()`.
    Immediate,
    /// Backend defers resize to next `render_frame()`.
    Deferred,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PauseSemantics {
    /// Full freeze — no logic, no frames.
    Freeze,
    /// Internal logic continues, frames stop.
    LogicOnly,
    /// Backend does not support pause.
    Unsupported,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ContentTypeHint {
    None,
    /// Static image — compositor hint `photo`.
    Photo,
    // TODO 0.2: Video — compositor hint `video`.
}

#[derive(Clone, Debug)]
pub struct BackendCapabilities {
    pub source_kind: FrameSourceKind,
    pub resize: ResizePolicy,
    pub pause_semantics: PauseSemantics,
    pub content_type_hint: ContentTypeHint,
    // TODO 0.2: pub input: InputSupport
    // TODO 0.2: pub damage: DamageSupport
}
