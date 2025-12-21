# mihomo-start

[原神](https://wiki.metacubex.one/)，启动

## Stand-Alone (Windows, Linux)

### Requirements

- python3.12 or above
- PyYaml installed (`pip install PyYaml` or `apt install python3-yaml`)
- Jinja2 installed (`pip install Jinja2` or `apt install python3-jinja2`)
- pyjson5 installed (`pip install pyjson5`)

or use [uv](https://docs.astral.sh/uv/)

### File Structure

```bash
├── mihomo-start                    * MAIN * [Default Working Directory]
│   ├── src
│   │   ├── subscribe_tool
|   |   
│   ├── assets
│   │   ├── 
|   |
|   ├── var
|   |   ├── config.template.yaml    * PREPARED *
|   |   ├── subscribe-tool.json     * GENERATED * @[Default Working Directory]
|   |   ├── run
|   |   |   ├── <binary>            * INSTALL *
|   |   |   ├── config	            * GENERATED *
|   |   |   ├── <resoucre>          * INSTALL *
|   |   |   ├── <ui>                * PREPARED *
|   |   |   |   ├── 
|   |   |
|   |   ├── cache
|   |   |
|   |   ├── logs
|   |   |
```




## TODO

