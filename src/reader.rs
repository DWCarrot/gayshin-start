use std::collections::HashMap;
use std::io;
use std::path::Path;

use case_insensitive_string::CaseInsensitiveString;
use libsubconverter::models::ProxyGroupConfig;
use libsubconverter::models::RulesetContent;
use libsubconverter::parser::explodes::explode_conf_content;
use libsubconverter::utils::http::HttpError;
use libsubconverter::utils::http::ProxyConfig;
use libsubconverter::utils::http_std;
use libsubconverter::Proxy;

use crate::extdata::clash::transform_to_model_ruleset;

pub struct Reader {
    name: Box<str>,
    content: Box<str>,
}


impl Reader {

    pub async fn download(
        name: &str,
        url: &str,
        proxy_config: Option<&ProxyConfig>,
        headers: Option<&HashMap<CaseInsensitiveString, String>>
    ) -> Result<Self, HttpError> {
        let proxy_config = if let Some(pc) = proxy_config {
            &pc
        } else {
            &ProxyConfig::default()
        };
        let resp = http_std::web_get_async(url, proxy_config, headers).await?;
        if (200..300).contains(&resp.status) {
            Ok(Reader { name: Box::from(name.to_string()), content: Box::from(resp.body) })
        } else {
            Err(HttpError { status: Some(resp.status), message: format!("Failed to download file: {}", resp.body) })?
        }
    }

    pub async fn dump(
        &self,
        file_path: &Path,
    ) -> Result<(), io::Error> {
        tokio::fs::write(file_path, self.content.as_bytes()).await
    }

    pub fn parse_nodes(&self) -> Vec<Proxy> {
        let mut nodes = Vec::new();
        let i = explode_conf_content(&self.content, &mut nodes);
        nodes
    }

    pub fn parse_groups(&self) -> Option<(Vec<ProxyGroupConfig>, Vec<RulesetContent>)> {
        let content = self.content.as_ref();
        if content.contains("proxies:") || content.contains("Proxy:") {
            self.parse_groups_and_ruleset_from_clash(content)
        } else {
            None
        }
    }

    fn parse_groups_and_ruleset_from_clash(&self, content: &str) -> Option<(Vec<ProxyGroupConfig>, Vec<RulesetContent>)> {
        use crate::extdata::clash::ClashProxyGroupAndRules;
        use crate::extdata::clash::transform_to_model_proxy_group;

        let clash_data: ClashProxyGroupAndRules = match serde_yaml::from_str(content) {
            Ok(data) => data,
            Err(_) => return None,
        };
        let mut groups = Vec::with_capacity(clash_data.proxy_groups.len());
        for group in clash_data.proxy_groups {
            match transform_to_model_proxy_group(group) {
                Ok(g) => groups.push(g),
                Err(_) => {}
            }
        }
        let mut rulesets = Vec::with_capacity(1);
        match transform_to_model_ruleset(self.name.as_ref(), clash_data.rules) {
            Ok(rs) => rulesets.push(rs),
            Err(_) => {}   
        }
        Some((groups, rulesets))
    }
}

