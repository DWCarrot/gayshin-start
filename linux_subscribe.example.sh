#!/bin/bash

python3 ./mihomo-start/scripts/main.py \
    --timeout 15000 \
    --cache ./subscribe_cache \
    --template ./config.template.yaml \
    --target-type clash \
    -Dallow_lan:bool=true \
    ./subscribe.json