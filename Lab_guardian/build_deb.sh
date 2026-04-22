#!/usr/bin/env bash
# =============================================================================
# build_deb.sh  —  Build the Lab Guardian standalone .deb package
#
# This script:
#   1. Installs PyInstaller (and app Python deps) into a clean venv
#   2. Runs PyInstaller to compile a single-file binary (dist/lab_guardian)
#   3. Assembles the Debian package directory tree
#   4. Calls dpkg-deb to produce:  lab-guardian_1.0.0_amd64.deb
#
# Usage (run from Lab_guardian/ directory):
#   bash build_deb.sh
#
# Output:
#   lab-guardian_1.0.0_amd64.deb   — ready to distribute
#
# Requirements on the BUILD machine only (NOT on end-user machines):
#   python3, python3-venv, dpkg-deb
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
step()  { echo -e "\n${BOLD}${CYAN}══ $* ══${NC}"; }

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="lab-guardian"
PKG_VERSION="1.0.0"
ARCH="amd64"
DEB_FILENAME="${PKG_NAME}_${PKG_VERSION}_${ARCH}.deb"

BUILD_VENV="${SCRIPT_DIR}/.build_venv"
PYINSTALLER_DIST="${SCRIPT_DIR}/dist"
BINARY_PATH="${PYINSTALLER_DIST}/lab_guardian"

# Staging directory — mirrors the filesystem layout inside the .deb
STAGING="${SCRIPT_DIR}/.deb_staging/${PKG_NAME}_${PKG_VERSION}_${ARCH}"

# ---------------------------------------------------------------------------
# Step 0: Pre-flight checks
# ---------------------------------------------------------------------------
step "Step 0: Pre-flight checks"

# ── Validate project structure FIRST ────────────────────────────────────────
# This script must be run from inside the Lab_guardian/ project folder,
# NOT copied alone to another directory.
MISSING_FILES=()
[ ! -f "${SCRIPT_DIR}/requirements.txt" ]         && MISSING_FILES+=("requirements.txt")
[ ! -f "${SCRIPT_DIR}/main.py" ]                  && MISSING_FILES+=("main.py")
[ ! -f "${SCRIPT_DIR}/lab_guardian.spec" ]         && MISSING_FILES+=("lab_guardian.spec")
[ ! -d "${SCRIPT_DIR}/lab_guardian" ]             && MISSING_FILES+=("lab_guardian/ (package directory)")
[ ! -f "${SCRIPT_DIR}/debian/postinst" ]           && MISSING_FILES+=("debian/postinst")
[ ! -f "${SCRIPT_DIR}/debian/prerm" ]              && MISSING_FILES+=("debian/prerm")
[ ! -f "${SCRIPT_DIR}/debian/lab_guardian.desktop" ] && MISSING_FILES+=("debian/lab_guardian.desktop")

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "${RED}[ERROR]${NC} This script requires the full Lab_guardian project folder." >&2
    echo -e "${RED}[ERROR]${NC} The following required files/dirs are missing from:" >&2
    echo -e "${RED}[ERROR]${NC}   ${SCRIPT_DIR}/" >&2
    echo "" >&2
    for f in "${MISSING_FILES[@]}"; do
        echo -e "          ${RED}✗${NC}  ${f}" >&2
    done
    echo "" >&2
    echo -e "${YELLOW}[FIX]${NC}   Copy the entire Lab_guardian/ folder to this machine, then run:" >&2
    echo -e "          cd Lab_guardian/" >&2
    echo -e "          bash build_deb.sh" >&2
    echo "" >&2
    exit 1
fi
ok "Project structure validated"

# ── System tool checks ───────────────────────────────────────────────────────
command -v python3 > /dev/null 2>&1 || error "python3 not found. Install it with: sudo apt install python3"
command -v dpkg-deb > /dev/null 2>&1 || error "dpkg-deb not found. Install it with: sudo apt install dpkg"

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python ${PYTHON_VERSION} found"

# Check python3-venv / python3-tk on the BUILD machine
if ! python3 -c "import venv" 2>/dev/null; then
    warn "python3-venv not found, installing..."
    sudo apt-get install -y "python${PYTHON_VERSION}-venv" || sudo apt-get install -y python3-venv
fi

if ! python3 -c "import tkinter" 2>/dev/null; then
    warn "python3-tk not found on build machine, installing..."
    sudo apt-get install -y "python${PYTHON_VERSION}-tk" || sudo apt-get install -y python3-tk
fi

ok "Pre-flight checks passed"

# ---------------------------------------------------------------------------
# Step 1: Create an isolated build venv and install all deps + PyInstaller
# ---------------------------------------------------------------------------
step "Step 1: Create build virtual environment"

if [ -d "$BUILD_VENV" ]; then
    info "Removing existing build venv..."
    rm -rf "$BUILD_VENV"
fi

python3 -m venv "$BUILD_VENV"
source "${BUILD_VENV}/bin/activate"

info "Installing application dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r "${SCRIPT_DIR}/requirements.txt"

info "Installing the lab_guardian package in editable mode..."
pip install --quiet -e "${SCRIPT_DIR}"

info "Installing PyInstaller..."
pip install --quiet pyinstaller

ok "Build venv ready: ${BUILD_VENV}"

# ---------------------------------------------------------------------------
# Step 2: Run PyInstaller
# ---------------------------------------------------------------------------
step "Step 2: Compile standalone binary with PyInstaller"

# Clean any previous build artifacts
rm -rf "${SCRIPT_DIR}/build" "${SCRIPT_DIR}/dist"

info "Running PyInstaller (this may take 1–3 minutes)..."
pyinstaller \
    --clean \
    --noconfirm \
    "${SCRIPT_DIR}/lab_guardian.spec"

deactivate

if [ ! -f "$BINARY_PATH" ]; then
    error "PyInstaller build failed — binary not found at: ${BINARY_PATH}"
fi

BINARY_SIZE=$(du -sh "$BINARY_PATH" | cut -f1)
ok "Binary compiled: ${BINARY_PATH}  (${BINARY_SIZE})"

# ---------------------------------------------------------------------------
# Step 3: Assemble the Debian package staging directory
# ---------------------------------------------------------------------------
step "Step 3: Assemble Debian package structure"

# Wipe and recreate staging
rm -rf "${SCRIPT_DIR}/.deb_staging"
mkdir -p "${STAGING}/DEBIAN"
mkdir -p "${STAGING}/usr/bin"
mkdir -p "${STAGING}/usr/share/applications"
mkdir -p "${STAGING}/usr/share/pixmaps"

# ── Binary ────────────────────────────────────────────────────────────────
cp "$BINARY_PATH" "${STAGING}/usr/bin/lab_guardian"
chmod 0755 "${STAGING}/usr/bin/lab_guardian"
ok "Binary → /usr/bin/lab_guardian"

# ── Application icon ──────────────────────────────────────────────────────
ICON_SRC="${SCRIPT_DIR}/assets/icon.png"
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "${STAGING}/usr/share/pixmaps/lab_guardian.png"
    ok "Icon → /usr/share/pixmaps/lab_guardian.png"
else
    warn "No assets/icon.png found — application icon will be missing"
fi

# ── Desktop launcher ──────────────────────────────────────────────────────
cp "${SCRIPT_DIR}/debian/lab_guardian.desktop" \
   "${STAGING}/usr/share/applications/lab_guardian.desktop"
chmod 0644 "${STAGING}/usr/share/applications/lab_guardian.desktop"
ok "Desktop entry → /usr/share/applications/lab_guardian.desktop"

# ── DEBIAN/ control files ─────────────────────────────────────────────────
# Calculate installed size (in KB) for the control file
INSTALLED_KB=$(du -sk "${STAGING}/usr" | cut -f1)

# Write control file with accurate installed size
cat > "${STAGING}/DEBIAN/control" << EOF
Package: ${PKG_NAME}
Version: ${PKG_VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: iproute2, libx11-6, libxext6, libxrender1, libtk8.6 | libtk
Recommends: auditd
Maintainer: Lab Insight Team <labinsight@example.com>
Description: Lab Guardian — Student monitoring agent (standalone binary)
 Lab Guardian is a fully self-contained executable that monitors student
 activity during lab examinations. It tracks running processes, connected
 USB storage devices, browser history, and terminal network commands.
 .
 This package bundles Python 3, SQLite, psutil, requests, pyudev, netifaces
 and all other Python dependencies — no Python installation is required.
 .
 System dependencies (auditd, iproute2) are installed automatically.
Installed-Size: ${INSTALLED_KB}
EOF

# Copy and chmod the maintainer scripts
cp "${SCRIPT_DIR}/debian/postinst" "${STAGING}/DEBIAN/postinst"
cp "${SCRIPT_DIR}/debian/prerm"    "${STAGING}/DEBIAN/prerm"
chmod 0755 "${STAGING}/DEBIAN/postinst"
chmod 0755 "${STAGING}/DEBIAN/prerm"
ok "DEBIAN/ control files installed"

# ---------------------------------------------------------------------------
# Step 4: Build the .deb package
# ---------------------------------------------------------------------------
step "Step 4: Build the .deb package"

DEB_OUTPUT="${SCRIPT_DIR}/${DEB_FILENAME}"
dpkg-deb --build --root-owner-group "${STAGING}" "${DEB_OUTPUT}"

if [ ! -f "$DEB_OUTPUT" ]; then
    error "dpkg-deb failed — .deb file not created"
fi

DEB_SIZE=$(du -sh "$DEB_OUTPUT" | cut -f1)
ok "Package built: ${DEB_OUTPUT}  (${DEB_SIZE})"

# ---------------------------------------------------------------------------
# Step 5: Verify the package
# ---------------------------------------------------------------------------
step "Step 5: Package verification"

info "Package info:"
dpkg-deb --info "${DEB_OUTPUT}"

info "Package contents:"
dpkg-deb --contents "${DEB_OUTPUT}"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Build complete!                                              ║${NC}"
echo -e "${GREEN}║                                                               ║${NC}"
echo -e "${GREEN}║  Package: ${DEB_FILENAME}${NC}"
echo -e "${GREEN}║  Size:    ${DEB_SIZE}${NC}"
echo -e "${GREEN}║                                                               ║${NC}"
echo -e "${GREEN}║  To install:                                                  ║${NC}"
echo -e "${GREEN}║    sudo apt install ./${DEB_FILENAME}       ║${NC}"
echo -e "${GREEN}║                                                               ║${NC}"
echo -e "${GREEN}║  To run:                                                      ║${NC}"
echo -e "${GREEN}║    lab_guardian                                               ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
