#!/bin/bash

echo "#### Update Subscribes ####"

python3 ./scripts/main.py \
    --timeout 15000 \
    --cache ../subscribe_cache \
    --template ../config.template.yaml \
    --target-type clash \
    -Dallow_lan:bool=true \
    -Denable_tun:bool=false \
    ./subscribe.json

echo "#### Launch Clash ####"

clash.meta -d ../
