use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct Config {

    #[serde(rename = "subscribe")]
    pub subscribes: Vec<Subscribe>,


}


fn default_enabled() -> bool {
    true
}

fn default_use_rules() -> bool {
    false
}

#[derive(Debug, Deserialize)]
pub struct Subscribe {

    pub name: String,
    
    pub url: String,
    
    #[serde(default = "default_enabled")]
    pub enabled: bool,

    #[serde(rename = "use-rules", default = "default_use_rules")]
    pub use_rules: bool,
}