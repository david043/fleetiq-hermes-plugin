#!/usr/bin/env bash
# Installs the FleetIQ observer plugin for Hermes (macOS/Linux/WSL/Git Bash).
#
# Usage:
#   FLEETIQ_URL=https://your-fleetiq-host FLEETIQ_API_KEY=fliq_sk_... ./install.sh
#
# Or answer the prompts interactively if the env vars aren't set.
set -e

REPO_RAW="https://raw.githubusercontent.com/david043/fleetiq-hermes-plugin/main"

if [ -z "$FLEETIQ_URL" ]; then
    read -rp "FleetIQ URL (e.g. https://fleetiq.example.com): " FLEETIQ_URL
fi
if [ -z "$FLEETIQ_API_KEY" ]; then
    read -rp "FleetIQ API key: " FLEETIQ_API_KEY
fi
if [ -z "$FLEETIQ_URL" ] || [ -z "$FLEETIQ_API_KEY" ]; then
    echo "FLEETIQ_URL and FLEETIQ_API_KEY are both required." >&2
    exit 1
fi
FLEETIQ_PROJECT_ID="${FLEETIQ_PROJECT_ID:-hermes}"

echo "Installing FleetIQ Hermes plugin..."

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
PLUGIN_DIR="$HERMES_HOME/plugins/fleetiq"
mkdir -p "$PLUGIN_DIR"

curl -fsSL "$REPO_RAW/plugin.yaml" -o "$PLUGIN_DIR/plugin.yaml"
curl -fsSL "$REPO_RAW/__init__.py" -o "$PLUGIN_DIR/__init__.py"

# ── Wire credentials into ~/.hermes/.env (idempotent upsert) ────────────────
ENV_FILE="$HERMES_HOME/.env"
touch "$ENV_FILE"
python3 - "$ENV_FILE" "$FLEETIQ_URL" "$FLEETIQ_API_KEY" "$FLEETIQ_PROJECT_ID" <<'PY'
import sys
path, url, key, project = sys.argv[1:5]
with open(path) as f:
    lines = f.read().splitlines()

def upsert(lines, name, value):
    prefix = name + "="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{name}={value}"
            return lines
    lines.append(f"{name}={value}")
    return lines

lines = upsert(lines, "FLEETIQ_URL", url)
lines = upsert(lines, "FLEETIQ_API_KEY", key)
lines = upsert(lines, "FLEETIQ_PROJECT_ID", project)
with open(path, "w") as f:
    f.write("\n".join(lines) + "\n")
print("wrote", path)
PY

# ── Enable the plugin (Hermes plugins are opt-in) ────────────────────────────
if command -v hermes >/dev/null 2>&1; then
    hermes plugins enable fleetiq || true
else
    echo "hermes CLI not found on PATH — enable manually: hermes plugins enable fleetiq"
fi

echo ""
echo "FleetIQ installed. Start a new Hermes session and it will appear on your dashboard."
echo "  Events -> $FLEETIQ_URL"
