#!/bin/bash
# Easy Installer for Lab Guardian Agent
# Usage: sudo bash install.sh

set -e

echo "========================================="
echo "🛡️ Lab Guardian Agent Installer"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Error: Please run with sudo"
    echo "   Usage: sudo bash install.sh"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DEB_FILE="$SCRIPT_DIR/lab-guardian-agent-2.0.0.deb"

# Check if .deb file exists
if [ ! -f "$DEB_FILE" ]; then
    echo "❌ Error: Package file not found!"
    echo "   Expected: $DEB_FILE"
    echo ""
    echo "Make sure install.sh and lab-guardian-agent-2.0.0.deb are in the same directory."
    exit 1
fi

# Step 1: Update package list
echo "📦 Step 1/4: Updating package list..."
apt-get update -qq

# Step 2: Install dependencies
echo "🔧 Step 2/4: Installing dependencies..."
apt-get install -y python3 python3-venv python3-pip

# Step 3: Install the agent
echo "📥 Step 3/4: Installing Lab Guardian Agent..."
dpkg -i "$DEB_FILE"

# Fix any remaining dependency issues
apt-get install -f -y

# Step 4: Verify installation
echo "✅ Step 4/4: Verifying installation..."
if dpkg -l lab-guardian-agent 2>/dev/null | grep -q "^ii"; then
    echo ""
    echo "========================================="
    echo "✅ Installation Successful!"
    echo "========================================="
    echo ""
    echo "📝 How to start the agent:"
    echo ""
    echo "   Option 1: From Applications Menu"
    echo "   Search for: 'Lab Guardian Agent'"
    echo ""
    echo "   Option 2: From Terminal"
    echo "   Run: lab-guardian start"
    echo ""
    echo "📌 Quick Guide:"
    echo "   1. Launch the agent"
    echo "   2. Enter your Roll Number"
    echo "   3. Select your Lab Number (L01-L12)"
    echo "   4. Click 'Start Exam Session'"
    echo ""
    echo "⚠️  Important:"
    echo "   - You cannot close the session yourself"
    echo "   - Teacher will provide a secret key to end the exam"
    echo "   - Do NOT try to kill the process"
    echo ""
    echo "🆘 Need help? Raise your hand for the invigilator."
    echo ""
else
    echo ""
    echo "❌ Installation failed!"
    echo "Please check the errors above and try again."
    exit 1
fi
