# Context Foundry build service -- homelab runtime image.
#
# Multi-stage: compile the `foundry` binary, then ship a slim runtime with the
# docker CLI (required by the local_docker backend to launch builder/preview
# containers on the host daemon).
#
# NOTE: this Dockerfile builds with default features only -- it never compiles
# the Azure dependency tree. The Azure deployment does NOT use this Dockerfile;
# it builds with `cargo build --release --features azure` per deploy/azure/.

FROM rust:1-bookworm AS builder
WORKDIR /src
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
# docker.io for the local_docker backend; curl + ca-certificates for
# healthchecks and outbound TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl docker.io \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /src/target/release/foundry /usr/local/bin/foundry
# migrations/ is copied so sqlx::migrate! finds it relative to the working dir.
COPY --from=builder /src/migrations /migrations
WORKDIR /
EXPOSE 8787 8788
ENTRYPOINT ["foundry"]
CMD ["serve"]
