use std::collections::BTreeMap;
use std::sync::OnceLock;

#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum SupportLevel {
    Unsupported,
    Detected,
    Partial,
    Full,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum ImageFormat {
    Png,
    Jpeg,
    Webp,
    Unknown,
}

// TODO 0.2: pub enum VideoCodec { H264, H265, Vp9, Av1, Unknown }
// TODO 0.2: pub enum ShaderFeature { ShadertoyUniforms, TextureChannels, MouseInput, Unknown }

pub struct SupportMatrix {
    pub image_formats: BTreeMap<ImageFormat, SupportLevel>,
    // TODO 0.2: video_codecs, shader_features
}

impl SupportMatrix {
    pub fn current() -> &'static SupportMatrix {
        static MATRIX: OnceLock<SupportMatrix> = OnceLock::new();
        MATRIX.get_or_init(default_matrix)
    }
}

fn default_matrix() -> SupportMatrix {
    use SupportLevel::*;
    SupportMatrix {
        image_formats: [
            (ImageFormat::Png, Full),
            (ImageFormat::Jpeg, Full),
            (ImageFormat::Webp, Full),
            (ImageFormat::Unknown, Unsupported),
        ]
        .into_iter()
        .collect(),
    }
}
