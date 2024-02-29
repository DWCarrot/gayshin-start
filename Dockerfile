FROM golang:1.22 AS builder

ARG TARGETPLATFORM
ARG CORE_TAG=v1.18.1
ARG DASHBOARD_TAG=v1.135.0

WORKDIR /workspace

RUN \
    echo "I'm building for ${TARGETPLATFORM} with core ${CORE_TAG}"; \
    git clone https://github.com/MetaCubeX/mihomo.git -b Meta; \
    cd mihomo/; \
    git checkout ${CORE_TAG}; \
    go env -w GOPROXY=https://goproxy.io,direct; \
    go mod download; \
    go build -v -a -o "build/clash.meta"

WORKDIR /workspace

RUN git clone https://github.com/MetaCubeX/meta-rules-dat.git -b release

WORKDIR /workspace

RUN \
    git clone https://github.com/metacubex/metacubexd.git -b gh-pages; \
    cd metacubexd/; \
    git checkout ${DASHBOARD_TAG}; \
    rm -r .git


FROM python:3.10-slim AS runner

RUN pip3 install PyYaml;
COPY --from=builder /workspace/mihomo/build/clash.meta /usr/local/bin/
COPY --from=builder /workspace/meta-rules-dat/geoip.metadb /workspace/meta-rules-dat/geoip.dat /workspace/meta-rules-dat/geosite.dat /var/lib/clash/
COPY --from=builder /workspace/metacubexd/ /var/lib/clash/metacubexd/
COPY ./ /var/lib/clash/mihomo-start

EXPOSE 1080 9090 8853

WORKDIR /var/lib/clash/mihomo-start

RUN \
    chmod +x /usr/local/bin/clash.meta; \
    chmod +x /var/lib/clash/mihomo-start/launch.sh

CMD [ "./docker_launch.sh" ]