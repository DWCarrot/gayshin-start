# mihomo-start

[原神](https://wiki.metacubex.one/)，启动

## Stand-Alone (Windows, Linux)

### Requirements

- python3.8 or above
- PyYaml installed (`pip install PyYaml` or `apt install python3-yaml`)

### File Structure

```bash
├── mihomo                                                  [require download]
├── geo*.(dat|metadb)                                       [require download]
├── mihomo-start                    * MAIN *
│   ├── install
│   │   ├── *.install.py
│   │   ├── *.service
│   │   ├── *.timer
│   │   ├── *.subscribe.sh
│   │   ├── util.py
│   ├── scripts
│   │   ├── *.py
│   ├── templates
│   │   ├── config.template.example.yaml
├── metacubexdb                                             [require download]
│   ├── *.*
├── subscribe.json                                          [require prepare]
├── config.template.yaml                                    [require prepare]
├── subscribe_cache                 * GENERATED LATER *
│   ├── 
├── cache.db                        * GENERATED LATER *
├── <*>.subscribe.sh                * GENERATED INSTALL *
├── <*>.service                     * GENERATED INSTALL *
├── <*>.timer                       * GENERATED INSTALL *
```

### Install & Run

- core binary should be downloaded manually.
- geo*.(dat|metadb) should be downloaded manually.
- metacubexdb should be downloaded manually from gh-pages branch and rename to `metacubexdb`.
- subscribe.json should be prepared with your own subscription information.
- config.template.yaml should be prepared with your own configuration. the example is in `mihomo-start/templates/config.template.example.yaml`.
  - variables can be used in config templates. using format like `!var ${<name>[:<type>]}[=default]` where the type should in `str int float bool`, default type is str and default value is `null`.
- put `mihomo-start` to corresponding directory 
- run `mihomo-start/install/*.install.py` to install service and timer
  - follow the guide of `mihomo-start/install/*.install.py`. notice that value in `[ ]` means default and if you want to use default value, you can just press enter.
  - `<*>.subscribe.sh` ,  `<*>.service`, `<*>.timer` will be generated.
  - _for linux service_ copy service and timer to corresponding directory as `mihomo-start/install/*.install.py` guide at the end.
- modify `config.template.yaml` if necessary. 
  - this modification can be done anytime before a service is started.
- try to run `<*>.subscribe.sh` to test if tools are working.
- enable and start sevice.

## Docker

### Image

TODO

### File Structure

```bash
/
├── usr 
│   ├── local
│   │   ├── bin
│   │   │   ├── mihomo
├── var 
│   ├── lib
│   │   ├── <*>
│   │   │   ├── mihomo-start
│   │   │   │   ├── scripts
│   │   │   │   │   ├── *.py
│   │   │   │   ├── docker_launch.sh
│   │   │   ├── geo*.(dat|metadb)
│   │   │   ├── metacubexdb
│   │   │   │   ├── *.*
│   │   │   ├── subscribe.json                                              [require prepare and bind from host] 
│   │   │   ├── config.template.yaml                                        [require prepare and bind from host]
│   │   │   ├── subscribe_cache                     * GENERATED LATER *     [require bind to host]
│   │   │   │   ├──                                 * GENERATED LATER *     [require bind to host]
│   │   │   ├── cache.db                            * GENERATED LATER *     [require bind to host]
```

### Install & Run

TODO


## TODO

- [ ] Docker