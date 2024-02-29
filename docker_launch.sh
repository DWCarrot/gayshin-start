#!/bin/bash

echo "#### Update Subscribes ####"

python3 ./scripts/main.py \
    --timeout 15000 \
    --cache ../cache \
    --template ./templates/config.template.yaml \
    --target-type clash \
    -Dallow_lan:bool=true \
    -Dweb_host=0.0.0.0:9090 \
    -Dweb_root=../metacubexd \
    -Dweb_secret=${DASHBOARD_SECRET} \
    -Ddns_host=0.0.0.0:8853 \
    -Denable_tun:bool=false \
    ./subscribe.json

echo "#### Launch Clash ####"

clash.meta -d ../
