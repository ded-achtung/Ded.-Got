#[derive(Debug, Clone)]
pub struct IgnoredItem {
    pub category: &'static str,
    pub identifier: String,
    pub reason: &'static str,
}
