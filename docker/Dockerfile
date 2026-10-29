# syntax=docker/dockerfile:1
# Tested image running webchanges from the source checkout, scheduled by the busybox crond inside the container.
# Build from the webchanges repository root (BuildKit picks up docker/Dockerfile.dockerignore):
#   docker build -f docker/Dockerfile -t webchanges .
# No browser: Playwright does not support Alpine (musl), so `use_browser: true` jobs fail.

FROM python:alpine AS builder

# Compilers for the dependencies without ready-made musl wheels for the newest Python (e.g. jq, PyYAML)
RUN apk add --no-cache gcc libffi-dev make musl-dev

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    VIRTUAL_ENV=/opt/venv

COPY . /src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv --python /usr/local/bin/python3 "$VIRTUAL_ENV" \
    && uv pip install \
    "/src[beautify,bs4,html5lib,ical2text,jq,pushover,curl_cffi,deepdiff_xml,pypdf,requests]" \
    python-dateutil


FROM python:alpine
ARG UID=1000

# tzdata: named time zones (`tz` in config.yaml, TZ environment variable); tini: reaps cron's children
RUN apk add --no-cache tini tzdata

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# webchanges' default locations (~/.config/webchanges and ~/.local/share/webchanges) both point to /data/webchanges,
# so that a plain `webchanges` run as user webchanges finds config.yaml, jobs.yaml, hooks.py and snapshots.db there.
# Alpine's root crontab only runs the empty /etc/periodic directories, so it is blanked.
RUN adduser -D -u "$UID" webchanges \
    && mkdir -p /data/webchanges /home/webchanges/.config /home/webchanges/.local/share \
    && ln -s /data/webchanges /home/webchanges/.config/webchanges \
    && ln -s /data/webchanges /home/webchanges/.local/share/webchanges \
    && chown -R webchanges:webchanges /data/webchanges /home/webchanges \
    && : > /etc/crontabs/root
VOLUME /data/webchanges

COPY docker/crontab /crontab
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["entrypoint.sh"]
