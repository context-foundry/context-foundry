# foundry-builder — the Context Foundry build-service builder image (M2 / T35.4).
#
# One image: `foundry` + Node + the `claude` CLI + git + common toolchains.
# The entrypoint establishes the Build Container Contract (clean HOME, no
# ambient ~/.claude.json, pinned git identity, service-owned .foundry.json) and
# runs `foundry run --no-tui --output-format json-stream`.
#
# Build context is this directory; the `foundry` release binary must be copied
# in first — see ./build.sh and ./README.md.
FROM node:22-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      git \
      curl \
      ca-certificates \
      jq \
      python3 \
      build-essential \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# The Claude CLI. No ~/.claude.json is baked in — the build container is
# authenticated only by the per-build proxy token injected at run time.
RUN npm install -g @anthropic-ai/claude-code

# The foundry engine binary (built with `cargo build --release`) and the
# Build Container Contract entrypoint.
COPY foundry /usr/local/bin/foundry
COPY entrypoint.sh /usr/local/bin/foundry-builder-entrypoint
RUN chmod +x /usr/local/bin/foundry /usr/local/bin/foundry-builder-entrypoint

# A non-root build user with a clean HOME — no host config can leak in.
RUN useradd --create-home --uid 10001 --shell /bin/bash builder \
  && mkdir -p /work \
  && chown builder:builder /work

USER builder
ENV HOME=/home/builder
WORKDIR /work

# Fail fast if a toolchain is missing.
RUN claude --version && foundry --version && git --version && node --version

ENTRYPOINT ["/usr/local/bin/foundry-builder-entrypoint"]
