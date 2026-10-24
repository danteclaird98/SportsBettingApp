# syntax=docker/dockerfile:1
FROM node:24-bookworm-slim AS research-build
WORKDIR /build
COPY next_app/research_runtime/package.json next_app/research_runtime/package-lock.json ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    npm ci --no-audit --no-fund
COPY next_app/research_runtime/ ./
RUN npm run build

FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 edgeboard \
    && mkdir -p /var/data && chown edgeboard:edgeboard /var/data
COPY --from=research-build /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY edgeodds/ ./edgeodds/
COPY next_app/server.py next_app/sources.json ./next_app/
COPY next_app/backup.py ./next_app/backup.py
COPY next_app/web/ ./next_app/web/
COPY next_app/reports/ ./next_app/reports/
COPY next_app/research_runtime/runtime.mjs ./next_app/research_runtime/runtime.mjs
COPY --from=research-build /build/dist/ ./next_app/research_runtime/dist/
COPY --from=research-build /build/build/ ./next_app/research_runtime/build/
COPY next_app/render-start.sh ./next_app/render-start.sh
RUN chmod -R a+rX /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=10000
USER edgeboard
EXPOSE 10000
ENTRYPOINT ["/usr/bin/tini", "-g", "--"]
CMD ["sh", "next_app/render-start.sh"]
