use std::fmt;

#[derive(Debug)]
pub enum BackendError {
    Decoder(DecoderError),
    ResourceExhausted,
    /// Invariant violation — this is a bug.
    InvalidState(&'static str),
}

impl fmt::Display for BackendError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Decoder(e) => write!(f, "decoder error: {}", e.0),
            Self::ResourceExhausted => write!(f, "resource exhausted"),
            Self::InvalidState(msg) => write!(f, "invalid state (bug): {msg}"),
        }
    }
}

impl std::error::Error for BackendError {}

#[derive(Debug, Clone)]
pub struct DecoderError(pub String);

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BackendStatus {
    /// Ready to render frames.
    Ready,
    /// Working with reduced functionality.
    Degraded,
    /// Cannot continue — OutputRuntime should recreate backend.
    Failed,
    /// Paused by request.
    Paused,
}
