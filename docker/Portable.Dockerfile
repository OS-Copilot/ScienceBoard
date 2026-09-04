ARG BASE_IMAGE=scienceboard-flat-rootfs:0.1
FROM ${BASE_IMAGE}

# docker export/import deliberately flattens the runtime filesystem so files
# removed by the sanitizing overlay cannot survive in a distributable lower
# layer. This file restores image metadata, which export does not preserve.
LABEL org.opencontainers.image.title="ScienceBoard desktop"
LABEL org.opencontainers.image.description="Containerized ScienceBoard 0.1 reference environment"
LABEL org.scienceboard.version="0.1"
LABEL org.scienceboard.distribution="sanitized-flat"

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:0 \
    HOME=/home/user \
    USER=user \
    LOGNAME=user \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US: \
    LC_NUMERIC=zh_CN.UTF-8 \
    LC_TIME=zh_CN.UTF-8 \
    LC_MONETARY=zh_CN.UTF-8 \
    LC_PAPER=zh_CN.UTF-8 \
    LC_NAME=zh_CN.UTF-8 \
    LC_ADDRESS=zh_CN.UTF-8 \
    LC_TELEPHONE=zh_CN.UTF-8 \
    LC_MEASUREMENT=zh_CN.UTF-8 \
    LC_IDENTIFICATION=zh_CN.UTF-8 \
    XDG_RUNTIME_DIR=/run/user/1000 \
    XDG_SESSION_TYPE=x11 \
    NO_AT_BRIDGE=0 \
    QT_ACCESSIBILITY=1 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    GALLIUM_DRIVER=llvmpipe \
    SCIENCEBOARD_SERVER_PORT=5000

EXPOSE 5000 8000

HEALTHCHECK --interval=5s --timeout=3s --start-period=20s --retries=30 \
    CMD curl -fsS http://127.0.0.1:5000/health >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/scienceboard-entrypoint"]
