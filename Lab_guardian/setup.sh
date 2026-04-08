#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh — Lab Guardian agent dependency installer
#
# Installs system packages, optional auditd rules for terminal command
# capture, and the Lab Guardian Python package.
#
# Usage:
#   sudo bash setup.sh          # Full install (including auditd rules)
#   bash setup.sh --no-auditd   # Skip auditd setup (no root required for agent)
# ---------------------------------------------------------------------------

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

SKIP_AUDITD=false
for arg in "$@"; do
    case "$arg" in
        --no-auditd) SKIP_AUDITD=true ;;
    esac
done

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
info "Installing system dependencies …"

PACKAGES=(
    python3
    python3-pip
    python3-venv
    iproute2       # provides ss
)

if [ "$SKIP_AUDITD" = false ]; then
    PACKAGES+=(auditd)
fi

if command -v apt-get &>/dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq "${PACKAGES[@]}"
    ok "System packages installed"
else
    warn "apt-get not found — please install manually: ${PACKAGES[*]}"
fi

# Ensure ss is available
if command -v ss &>/dev/null; then
    ok "ss command available ($(ss --version 2>&1 | head -1))"
else
    warn "ss command not found — Layer 1 (connection detection) will be disabled"
fi

# ---------------------------------------------------------------------------
# 2. Python dependencies
# ---------------------------------------------------------------------------
info "Installing Python dependencies …"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    pip3 install --quiet -r "$SCRIPT_DIR/requirements.txt"
    ok "Python requirements installed"
fi

# Install the package in editable mode
pip3 install --quiet -e "$SCRIPT_DIR"
ok "lab_guardian package installed"

# ---------------------------------------------------------------------------
# 3. auditd rules (optional, requires root)
# ---------------------------------------------------------------------------
if [ "$SKIP_AUDITD" = false ]; then
    info "Configuring auditd rules for terminal command capture …"

    if [ "$(id -u)" -ne 0 ]; then
        warn "Not running as root — skipping auditd rule setup"
        warn "Re-run with: sudo bash setup.sh"
    else
        RULES_DIR="/etc/audit/rules.d"
        RULES_FILE="$RULES_DIR/exam.rules"

        mkdir -p "$RULES_DIR"

        cat > "$RULES_FILE" <<'RULES'
## Lab Guardian — monitor network-capable terminal commands
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/curl    -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/wget    -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/git     -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/ssh     -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/python3 -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/pip3    -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/nc      -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/ncat    -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/socat   -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/node    -k exam_net
-a always,exit -F arch=b64 -S execve -F exe=/usr/bin/npm     -k exam_net
RULES

        ok "auditd rules written to $RULES_FILE"

        # Load rules immediately
        if command -v auditctl &>/dev/null; then
            auditctl -R "$RULES_FILE" 2>/dev/null || true
            ok "auditd rules loaded"
        fi

        # Ensure auditd is running
        if command -v systemctl &>/dev/null; then
            systemctl enable auditd 2>/dev/null || true
            systemctl restart auditd 2>/dev/null || true
            ok "auditd service enabled and restarted"
        fi

        # Make audit log readable by the agent (when not running as root)
        AUDIT_LOG="/var/log/audit/audit.log"
        if [ -f "$AUDIT_LOG" ]; then
            chmod o+r "$AUDIT_LOG"
            ok "Audit log made world-readable: $AUDIT_LOG"
        fi
    fi
else
    info "Skipping auditd setup (--no-auditd flag)"
fi

# ---------------------------------------------------------------------------
# 4. Verify installation
# ---------------------------------------------------------------------------
echo ""
info "Verifying installation …"

if command -v lab_guardian &>/dev/null; then
    ok "lab_guardian CLI available: $(lab_guardian --version 2>&1)"
else
    warn "lab_guardian not in PATH — try: pip3 install -e $SCRIPT_DIR"
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Lab Guardian setup complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Usage:"
echo "    lab_guardian join --roll-no CS2021001 --session-id <UUID>"
echo ""
if [ "$SKIP_AUDITD" = false ] && [ "$(id -u)" -eq 0 ]; then
    echo "  auditd rules are active — full terminal command capture enabled."
else
    echo "  Note: Run 'sudo bash setup.sh' to enable auditd command capture."
fi
echo ""
