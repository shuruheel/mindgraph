# Same Python/locked Hermes installation as the real-host CI gate.
FROM python:3.14.0-slim-trixie@sha256:0aecac02dc3d4c5dbb024b753af084cafe41f5416e02193f1ce345d671ec966e AS sqlite
# Match Hermes's pinned WAL-reset fix; distro SQLite predates it.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL --retry 3 https://sqlite.org/2026/sqlite-autoconf-3530400.tar.gz -o /tmp/sqlite.tar.gz \
    && echo '0e9483900e92cd5de8fd48d16bf9200145a61f7fd5be542a5ac81d8a9516eb9c  /tmp/sqlite.tar.gz' | sha256sum -c - \
    && tar -xzf /tmp/sqlite.tar.gz -C /tmp \
    && cd /tmp/sqlite-autoconf-3530400 \
    && CFLAGS='-O2 -DSQLITE_ENABLE_FTS5 -DSQLITE_ENABLE_COLUMN_METADATA -DSQLITE_ENABLE_RTREE' \
       ./configure --prefix=/opt/sqlite-fixed --disable-static \
    && make -j2 && make install

FROM python:3.14.0-slim-trixie@sha256:0aecac02dc3d4c5dbb024b753af084cafe41f5416e02193f1ce345d671ec966e
ARG HERMES_REF=ae1ff71c39d8527227400c8e71acf9c57a8a59c6
ARG PLUGIN_REF=2abbfd03b73c6e369ab645bcb747cc6804555507
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy \
    HERMES_HOME=/data/profile HOME=/data LD_LIBRARY_PATH=/opt/sqlite-fixed/lib
COPY --from=sqlite /opt/sqlite-fixed /opt/sqlite-fixed
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates gosu tini libatomic1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.13.8
RUN git init /opt/hermes && git -C /opt/hermes remote add origin https://github.com/NousResearch/hermes-agent.git \
    && git -C /opt/hermes fetch --depth=1 origin "$HERMES_REF" \
    && git -C /opt/hermes checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/hermes rev-parse HEAD)" = "$HERMES_REF"
WORKDIR /opt/hermes
RUN uv sync --locked --python /usr/local/bin/python3 --no-dev
RUN git init /opt/mindgraph-plugin && git -C /opt/mindgraph-plugin remote add origin https://github.com/shuruheel/mindgraph.git \
    && git -C /opt/mindgraph-plugin fetch --depth=1 origin "$PLUGIN_REF" \
    && git -C /opt/mindgraph-plugin checkout --detach FETCH_HEAD \
    && test "$(git -C /opt/mindgraph-plugin rev-parse HEAD)" = "$PLUGIN_REF" \
    && uv pip install --python /opt/hermes/.venv/bin/python mindgraph-sdk==0.17.0 pytest==9.2.0 \
    && uv cache clean \
    && useradd --uid 10000 --home-dir /data --shell /bin/bash hermes
COPY . /opt/lab/
RUN chmod 755 /opt/lab/*.sh \
    && ln -s /opt/lab/command.sh /usr/local/bin/hermes-lab \
    && /opt/hermes/.venv/bin/python -c 'import sqlite3; assert sqlite3.sqlite_version == "3.53.4", sqlite3.sqlite_version'
# A fresh volume hides image-created /data directories until entrypoint runs.
WORKDIR /opt/hermes
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/lab/entrypoint.sh"]
CMD ["sleep", "infinity"]
