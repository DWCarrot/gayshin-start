use clap::builder::Str;
use libsubconverter::models;
use serde::Deserialize;

/// ClashProxyGroup represents a serializable proxy group for Clash configurations
///
/// This struct is designed to be serialized directly to YAML for Clash configurations.
/// It contains all necessary fields with proper serde annotations to control when
/// fields are included in the output.
#[derive(Debug, Deserialize)]
pub struct ClashProxyGroup {
    /// Name of the proxy group
    pub name: String,

    /// Type of the proxy group (select, url-test, fallback, load-balance, etc.)
    #[serde(rename = "type")]
    pub group_type: String,

    /// List of proxy names in this group
    #[serde(default)]
    pub proxies: Vec<String>,

    /// List of provider names used by this group
    #[serde(rename = "use", default)]
    pub using_provider: Vec<String>,

    /// URL for testing (for url-test, fallback, and load-balance types)
    #[serde(default)]
    pub url: String,

    /// Interval in seconds between tests (for url-test, fallback, and load-balance types)
    #[serde(default = "default_u32_zero")]
    pub interval: u32,

    /// Timeout in seconds for tests
    #[serde(default = "default_u32_zero")]
    pub timeout: u32,

    /// Tolerance value for tests
    #[serde(default = "default_u32_zero")]
    pub tolerance: u32,

    /// Strategy for load balancing (for load-balance type)
    #[serde(default)]
    pub strategy: String,

    /// Whether to use lazy loading
    #[serde(default = "default_true")]
    pub lazy: bool,

    /// Whether to disable UDP support
    #[serde(rename = "disable-udp", default = "default_false")]
    pub disable_udp: bool,

    /// Whether to persist connections
    #[serde(default = "default_false")]
    pub persistent: bool,

    /// Whether to evaluate before use
    #[serde(rename = "evaluate-before-use", default = "default_false")]
    pub evaluate_before_use: bool,
}


fn default_true() -> bool {
    true
}

fn default_false() -> bool {
    false
}

fn default_u32_zero() -> u32 {
    0
}

pub fn transform_to_model_proxy_group(group: ClashProxyGroup) -> Result<models::ProxyGroupConfig, String> {
    let group_type = match group.group_type.as_str() {
        "select" => models::ProxyGroupType::Select,
        "url-test" => models::ProxyGroupType::URLTest,
        "fallback" => models::ProxyGroupType::Fallback,
        "load-balance" => models::ProxyGroupType::LoadBalance,
        "relay" => models::ProxyGroupType::Relay,
        _ => return Err(format!("Unknown group type: {}", group.group_type)),
    };
    let strategy = match group.strategy.as_str() {
        "round-robin" => models::BalanceStrategy::RoundRobin,
        "consistent-hashing" => models::BalanceStrategy::ConsistentHashing,
        _ => models::BalanceStrategy::ConsistentHashing, // Default to ConsistentHashing if unknown
    };
    Ok(models::ProxyGroupConfig {
        name: group.name,
        group_type,
        proxies: group.proxies,
        using_provider: group.using_provider,
        url: group.url,
        interval: group.interval,
        timeout: group.timeout,
        tolerance: group.tolerance,
        strategy,
        lazy: group.lazy,
        disable_udp: group.disable_udp,
        persistent: group.persistent,
        evaluate_before_use: group.evaluate_before_use,
    })
}

pub fn transform_to_model_ruleset(group: &str, rules: Vec<String>) -> Result<models::RulesetContent, String> {
    let content = rules.join("\r\n");
    Ok(models::RulesetContent {
        group: group.to_string(),
        rule_path: String::new(),
        rule_path_typed: String::new(),
        rule_type: models::RulesetType::default(),
        rule_content: std::sync::Arc::new(std::sync::RwLock::new(Some(content))),
        update_interval: 0,
    })
}

#[derive(Debug, Deserialize)]
pub struct ClashProxyGroupAndRules {

    #[serde(rename = "proxy-groups", default)]
    pub proxy_groups: Vec<ClashProxyGroup>,

    #[serde(default)]
    pub rules: Vec<String>,
}
