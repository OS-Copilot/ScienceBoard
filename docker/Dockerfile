ARG BASE_IMAGE=scienceboard-rootfs:0.1
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="ScienceBoard desktop"
LABEL org.opencontainers.image.description="Containerized ScienceBoard 0.1 reference environment"
LABEL org.scienceboard.version="0.1"

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

RUN install -d -m 1777 /tmp \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        at-spi2-core \
        dbus-x11 \
        mesa-utils \
        openbox \
        procps \
        x11-utils \
        xauth \
        xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f \
        /etc/ssh/ssh_host_* \
        /root/.bash_history \
        /root/.python_history \
        /home/user/.bash_history \
        /home/user/.python_history \
        /home/user/.config/Code/Cookies \
        /home/user/.config/Code/Cookies-journal \
        /home/user/.config/Code/Network\ Persistent\ State \
        /var/lib/systemd/random-seed \
        /etc/NetworkManager/system-connections/* \
    && find /home/user -xdev -type f \
        \( -name .bash_history -o -name .python_history \
           -o -name 'cookies.sqlite' -o -name 'cookies.sqlite-wal' \
           -o -name 'cookies.sqlite-shm' -o -name 'logins.json' \
           -o -name 'key4.db' -o -name 'formhistory.sqlite' \
           -o -name 'places.sqlite' -o -name 'places.sqlite-wal' \
           -o -name 'places.sqlite-shm' \) \
        -delete \
    && find /home/user -xdev -type d -name sessionstore-backups \
        -prune -exec rm -rf '{}' + \
    && rm -rf /home/user/.local/share/keyrings \
    && install -d -m 0700 -o user -g user \
        /home/user/.local/share/keyrings \
    && firefox_snap="$(find /var/lib/snapd/snaps -maxdepth 1 \
        -type f -name 'firefox_*.snap' -print | sort -V | tail -n 1)" \
    && test -n "$firefox_snap" \
    && firefox_revision="$(basename "$firefox_snap")" \
    && firefox_revision="${firefox_revision#firefox_}" \
    && firefox_revision="${firefox_revision%.snap}" \
    && unsquashfs -f -d /opt/firefox-snap "$firefox_snap" >/dev/null \
    && printf '%s\n' "$firefox_revision" \
        > /opt/firefox-snap/.scienceboard-revision \
    && rm -f /var/lib/snapd/snaps/firefox_*.snap \
    && rm -rf /home/user/.ssh \
    && install -d -m 0700 -o user -g user /home/user/.ssh \
    && : > /etc/machine-id \
    && rm -f /var/lib/dbus/machine-id \
    && install -d /var/lib/dbus \
    && ln -s /etc/machine-id /var/lib/dbus/machine-id \
    && install -d -o user -g user /home/user/server/screenshots

COPY vm_config/server.py /home/user/server/main.py
COPY vm_config/pyxcursor.py /home/user/server/pyxcursor.py
COPY docker/reset.sh /home/user/server/reset.sh
COPY docker/entrypoint.sh /usr/local/bin/scienceboard-entrypoint
COPY docker/session.sh /usr/local/bin/scienceboard-session
COPY docker/code-wrapper.sh /home/user/bin/code
COPY docker/firefox-wrapper.sh /usr/local/bin/scienceboard-firefox
COPY docker/firefox.desktop /usr/share/applications/firefox.desktop
COPY docker/firefox-policies.json /opt/firefox-snap/usr/lib/firefox/distribution/policies.json

RUN chmod 0755 \
        /usr/local/bin/scienceboard-entrypoint \
        /usr/local/bin/scienceboard-session \
        /usr/local/bin/scienceboard-firefox \
        /home/user/bin/code \
        /home/user/server/reset.sh \
    && chmod 0644 \
        /usr/share/applications/firefox.desktop \
        /opt/firefox-snap/usr/lib/firefox/distribution/policies.json \
    && rm -f /snap/bin/firefox \
    && ln -s /usr/local/bin/scienceboard-firefox /snap/bin/firefox \
    && ln -s /usr/local/bin/scienceboard-firefox /home/user/bin/firefox \
    && chown -R user:user /home/user/server /home/user/bin

EXPOSE 5000 8000

HEALTHCHECK --interval=5s --timeout=3s --start-period=20s --retries=30 \
    CMD curl -fsS http://127.0.0.1:5000/health >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/scienceboard-entrypoint"]
