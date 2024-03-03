#!/bin/bash

ARG_NO_UPDATE=""
if [ "$1" = "local" ]; then
    ARG_NO_UPDATE="--no-update"
fi

/usr/bin/python3 %repo_dir%/scripts/main.py \
    --timeout 15000 \
    --cache %clash_dir%/subscribe_cache \
    --template %repo_dir%/templates/config.template.yaml \
    --target-type clash \
    $ARG_NO_UPDATE \
    -Dallow_lan:bool=true \
    -Dweb_host=%ctrl_host% \
    -Dweb_root=%clash_dir%/metacubexd \
    -Dweb_secret=%ctrl_passwd% \
    -Ddns_host=0.0.0.0:8853 \
    %clash_dir%/subscribe.json