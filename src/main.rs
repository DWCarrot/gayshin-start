use libsubconverter::parser::parse_settings;

mod settings;
mod reader;
mod extdata;

#[actix_rt::main]
async fn main() {
    println!("Hello, world!");

    let cache_dir = "./cache";
    std::fs::create_dir_all(cache_dir).expect("Failed to create cache directory");

    // load config from config.toml
    let config_str = std::fs::read_to_string("settings/settings.toml").expect("Failed to read config.toml");
    let config: settings::Config = toml::from_str(&config_str).expect("Failed to parse config.toml");
    println!("{:#?}", config);


    test(&config).await;
}

async fn test(config: &settings::Config) {
    let mut group_id = 1;
    for sub in config.subscribes.iter().filter(|s| s.enabled) {
        println!("Processing subscription: {} - {}", sub.name, sub.url);
        // Here you can add your logic to process each subscription
        match reader::Reader::download(&sub.name, &sub.url, None, None).await {
            Ok(reader) => {
                let nodes = reader.parse_nodes();
                println!("Parsed {} nodes from subscription: {}", nodes.len(), sub.name);
                for node in nodes {
                    println!("Node: {:?}", node.remark);
                }

                if sub.use_rules {
                    if let Some((groups, rulesets)) = reader.parse_groups() {
                        println!("Parsed {} groups from subscription: {}", groups.len(), sub.name);
                        println!("Parsed {} rulesets from subscription: {}", rulesets.len(), sub.name);
                        for group in groups {
                            println!("Group: {:?}", group.name);
                        }
                    }
                }
            }
            Err(e) => {
                eprintln!("Failed to download subscription {}: {}", sub.name, e);
            }
        }
        group_id += 1;
    }
}

