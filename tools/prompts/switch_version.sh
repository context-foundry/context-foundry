#!/bin/bash
# Prompt Version Switcher - Switch between archived prompt versions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$(dirname "$SCRIPT_DIR")"
ARCHIVE_DIR="$SCRIPT_DIR/archive"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 [list|switch|backup|compare]"
    echo ""
    echo "Commands:"
    echo "  list                  - List all archived prompt versions"
    echo "  switch <version>      - Switch to a specific version (e.g., v1.0.0)"
    echo "  backup <name>         - Backup current version with custom name"
    echo "  compare <v1> <v2>     - Compare token counts between versions"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 switch v1.0.0"
    echo "  $0 backup my-experiment"
    echo "  $0 compare v1.0.0 v1.1.0"
    exit 1
}

list_versions() {
    echo -e "${GREEN}Available Prompt Versions:${NC}"
    echo ""

    if [ ! -d "$ARCHIVE_DIR" ]; then
        echo -e "${YELLOW}No archive directory found${NC}"
        return
    fi

    echo "Orchestrator Prompts:"
    ls -1 "$ARCHIVE_DIR"/orchestrator_prompt_*.txt 2>/dev/null | while read -r file; do
        version=$(basename "$file" | sed 's/orchestrator_prompt_//; s/.txt//')
        lines=$(wc -l < "$file")
        words=$(wc -w < "$file")
        tokens=$((words * 13 / 10))  # Rough estimate: 1.3 tokens per word
        echo "  - $version ($lines lines, ~$tokens tokens)"
    done

    echo ""
    echo "GitHub Agent Prompts:"
    ls -1 "$ARCHIVE_DIR"/github_agent_prompt_*.txt 2>/dev/null | while read -r file; do
        version=$(basename "$file" | sed 's/github_agent_prompt_//; s/.txt//')
        lines=$(wc -l < "$file")
        words=$(wc -w < "$file")
        tokens=$((words * 13 / 10))
        echo "  - $version ($lines lines, ~$tokens tokens)"
    done
}

switch_version() {
    local version="$1"

    if [ -z "$version" ]; then
        echo -e "${RED}Error: Version required${NC}"
        usage
    fi

    local orch_file="$ARCHIVE_DIR/orchestrator_prompt_${version}.txt"
    local github_file="$ARCHIVE_DIR/github_agent_prompt_${version}.txt"

    if [ ! -f "$orch_file" ]; then
        echo -e "${RED}Error: Orchestrator prompt version $version not found${NC}"
        echo "Available versions:"
        list_versions
        exit 1
    fi

    # Backup current version before switching
    echo -e "${YELLOW}Backing up current version...${NC}"
    backup_current "pre-switch-$(date +%Y%m%d-%H%M%S)"

    # Switch orchestrator prompt
    echo -e "${GREEN}Switching orchestrator prompt to $version...${NC}"
    cp "$orch_file" "$TOOLS_DIR/orchestrator_prompt.txt"

    # Switch GitHub agent prompt if exists
    if [ -f "$github_file" ]; then
        echo -e "${GREEN}Switching GitHub agent prompt to $version...${NC}"
        cp "$github_file" "$TOOLS_DIR/github_agent_prompt.txt"
    fi

    echo -e "${GREEN}✓ Switched to version $version${NC}"
    echo ""
    echo "Current versions:"
    head -2 "$TOOLS_DIR/orchestrator_prompt.txt" | tail -1
    head -2 "$TOOLS_DIR/github_agent_prompt.txt" | tail -1
}

backup_current() {
    local name="${1:-$(date +%Y%m%d-%H%M%S)}"

    echo -e "${YELLOW}Creating backup: $name${NC}"

    mkdir -p "$ARCHIVE_DIR"

    cp "$TOOLS_DIR/orchestrator_prompt.txt" "$ARCHIVE_DIR/orchestrator_prompt_${name}.txt"
    cp "$TOOLS_DIR/github_agent_prompt.txt" "$ARCHIVE_DIR/github_agent_prompt_${name}.txt"

    echo -e "${GREEN}✓ Backup created${NC}"
}

compare_versions() {
    local v1="$1"
    local v2="$2"

    if [ -z "$v1" ] || [ -z "$v2" ]; then
        echo -e "${RED}Error: Two versions required for comparison${NC}"
        usage
    fi

    local file1="$ARCHIVE_DIR/orchestrator_prompt_${v1}.txt"
    local file2="$ARCHIVE_DIR/orchestrator_prompt_${v2}.txt"

    if [ ! -f "$file1" ]; then
        echo -e "${RED}Error: Version $v1 not found${NC}"
        exit 1
    fi

    if [ ! -f "$file2" ]; then
        echo -e "${RED}Error: Version $v2 not found${NC}"
        exit 1
    fi

    echo -e "${GREEN}Comparing $v1 vs $v2:${NC}"
    echo ""

    local lines1=$(wc -l < "$file1")
    local lines2=$(wc -l < "$file2")
    local words1=$(wc -w < "$file1")
    local words2=$(wc -w < "$file2")
    local tokens1=$((words1 * 13 / 10))
    local tokens2=$((words2 * 13 / 10))

    echo "Version $v1:"
    echo "  Lines: $lines1"
    echo "  Words: $words1"
    echo "  Tokens (est): $tokens1"
    echo ""
    echo "Version $v2:"
    echo "  Lines: $lines2"
    echo "  Words: $words2"
    echo "  Tokens (est): $tokens2"
    echo ""

    local line_diff=$((lines2 - lines1))
    local word_diff=$((words2 - words1))
    local token_diff=$((tokens2 - tokens1))
    local token_pct=$((token_diff * 100 / tokens1))

    echo "Difference:"
    echo "  Lines: $line_diff"
    echo "  Words: $word_diff"
    echo "  Tokens: $token_diff ($token_pct%)"

    if [ $token_diff -lt 0 ]; then
        echo -e "  ${GREEN}✓ $v2 is smaller by ${token_diff#-} tokens${NC}"
    elif [ $token_diff -gt 0 ]; then
        echo -e "  ${YELLOW}⚠ $v2 is larger by $token_diff tokens${NC}"
    else
        echo "  ✓ Same size"
    fi
}

# Main command router
case "${1:-}" in
    list)
        list_versions
        ;;
    switch)
        switch_version "$2"
        ;;
    backup)
        backup_current "$2"
        ;;
    compare)
        compare_versions "$2" "$3"
        ;;
    *)
        usage
        ;;
esac
