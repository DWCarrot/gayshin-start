#!/bin/bash

ARG_NO_UPDATE=""
if [ "$1" = "local" ]; then
    ARG_NO_UPDATE="--no-update"
fi

/usr/bin/python3 %repo_dir%/scripts/main.py \
    --timeout 15000 \
    --cache %clash_dir%/subscribe_cache \
    --template %clash_dir%/config.template.yaml \
    --output %clash_dir%/config.yaml \
    --target-type clash \
    $ARG_NO_UPDATE \
    -Dallow_lan:bool=true \
    %clash_dir%/subscribe.json