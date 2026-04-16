#!/bin/bash
# build_deb.sh - Build Debian package for Lab Guardian Agent
# This script creates a standalone .deb file that students can install

set -e

echo "🛡️ Building Lab Guardian Agent Debian Package..."

# Configuration
PACKAGE_NAME="lab-guardian-agent"
VERSION="2.0.0"
ARCH="all"
BUILD_DIR="build/deb"
PACKAGE_DIR="$BUILD_DIR/$PACKAGE_NAME-$VERSION"

# Clean previous builds
rm -rf "$BUILD_DIR"
mkdir -p "$PACKAGE_DIR/DEBIAN"
mkdir -p "$PACKAGE_DIR/opt/lab-guardian"
mkdir -p "$PACKAGE_DIR/usr/bin"
mkdir -p "$PACKAGE_DIR/usr/share/applications"
mkdir -p "$PACKAGE_DIR/etc/lab-guardian"

# Copy agent files
echo "📦 Copying agent files..."
cp -r lab_guardian/* "$PACKAGE_DIR/opt/lab-guardian/"

# Create Python virtual environment with all dependencies
echo "🐍 Setting up Python environment..."
cd "$PACKAGE_DIR/opt/lab-guardian"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install PyQt5
cd ../../../..

# Create launcher script
cat > "$PACKAGE_DIR/opt/lab-guardian/start-agent.sh" << 'EOF'
#!/bin/bash
# Start Lab Guardian Agent with virtual environment
cd /opt/lab-guardian
source venv/bin/activate
python3 -m lab_guardian start "$@"
EOF
chmod +x "$PACKAGE_DIR/opt/lab-guardian/start-agent.sh"

# Create system-wide command
cat > "$PACKAGE_DIR/usr/bin/lab-guardian" << 'EOF'
#!/bin/bash
# System-wide launcher for Lab Guardian Agent
exec /opt/lab-guardian/start-agent.sh "$@"
EOF
chmod +x "$PACKAGE_DIR/usr/bin/lab-guardian"

# Create .desktop file for GUI
cat > "$PACKAGE_DIR/usr/share/applications/lab-guardian.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Lab Guardian Agent
Comment=Exam Monitoring Agent for Students
Exec=/opt/lab-guardian/start-agent.sh
Icon=/opt/lab-guardian/icon.png
Terminal=false
Categories=Education;
Keywords=exam;monitoring;lab;
EOF

# Create DEBIAN control file
cat > "$PACKAGE_DIR/DEBIAN/control" << EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: education
Priority: optional
Architecture: $ARCH
Depends: python3 (>= 3.9), python3-venv, python3-pip
Maintainer: Lab Guardian Team <admin@labguardian.com>
Description: Lab Guardian Exam Monitoring Agent
 Offline-first exam monitoring system for computer labs.
 Monitors student activities including processes, browser history,
 terminal commands, and USB devices during exam sessions.
EOF

# Create postinst script (runs after installation)
cat > "$PACKAGE_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

echo "🛡️ Lab Guardian Agent installed successfully!"
echo ""
echo "To start the agent:"
echo "  1. Launch from Applications menu: 'Lab Guardian Agent'"
echo "  2. Or run from terminal: lab-guardian start"
echo ""
echo "The agent will:"
echo "  - Store all data locally in ~/.lab_guardian/exam_data.db"
echo "  - Sync to backend when internet is available"
echo "  - Require secret key (80085) to end session"
echo ""
echo "For verbose logging:"
echo "  lab-guardian start -vv"

# Set proper permissions
chown -R root:root /opt/lab-guardian
chmod -R 755 /opt/lab-guardian

# Create default config
if [ ! -f /etc/lab-guardian/config ]; then
    cat > /etc/lab-guardian/config << 'CONF'
# Lab Guardian Agent Configuration
BACKEND_URL=http://localhost:8000
SYNC_INTERVAL=30
CONF
fi

exit 0
EOF
chmod +x "$PACKAGE_DIR/DEBIAN/postinst"

# Create prerm script (runs before removal)
cat > "$PACKAGE_DIR/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e

echo "🗑️ Removing Lab Guardian Agent..."

# Kill any running agent processes
if pgrep -f "lab_guardian" > /dev/null; then
    echo "Stopping running agent processes..."
    pkill -f "lab_guardian" || true
    sleep 2
fi

echo "Removal complete."
exit 0
EOF
chmod +x "$PACKAGE_DIR/DEBIAN/prerm"

# Build the package
echo "🔨 Building .deb package..."
cd "$BUILD_DIR"
dpkg-deb --build "$PACKAGE_NAME-$VERSION"

echo ""
echo "✅ Package built successfully!"
echo "📦 Location: $BUILD_DIR/${PACKAGE_NAME}-${VERSION}.deb"
echo ""
echo "To install on student machines:"
echo "  sudo dpkg -i ${PACKAGE_NAME}-${VERSION}.deb"
echo "  sudo apt-get install -f  # if dependencies are missing"
echo ""

cd ../..
