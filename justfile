# Context Foundry — command recipes
# Install just: https://github.com/casey/just

bin_name := "foundry"
install_dir := env("CARGO_HOME", "~/.cargo") / "bin"

# Debug build
build:
    cargo build

# Release build + install to PATH
install:
    cargo build --release
    cp target/release/{{bin_name}} {{install_dir}}/

# Alias for build
dev: build

# Type check + clippy lints
check:
    cargo check
    cargo clippy -- -D warnings

# Run tests
test:
    cargo test

# Run tests with output
test-verbose:
    cargo test -- --nocapture

# Clean build artifacts
clean:
    cargo clean

# Build + install + run in current directory
run: install
    {{bin_name}}

# Format code
fmt:
    cargo fmt

# Format check (CI)
fmt-check:
    cargo fmt -- --check
