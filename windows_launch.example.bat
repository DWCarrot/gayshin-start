python3 .\mihomo-start\scripts\main.py \
    --timeout 15000 \
    --cache .\subscribe_cache \
    --template .\mihomo-start\templates\config.template.yaml \
    --target-type clash \
    -Dallow_lan:bool=true \
    -Dweb_host=127.0.0.1:9090 \
    -Dweb_root=metacubexd-gh-pages \
    -Dweb_secret=${DASHBOARD_SECRET} \
    -Ddns_host=0.0.0.0:8853 \
    -Denable_tun:bool=false \
    .\subscribe.json