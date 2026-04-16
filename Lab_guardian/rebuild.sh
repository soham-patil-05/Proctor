#!/bin/bash
# Quick rebuild script - fixes installation and rebuilds the package

set -e

echo "🔧 Lab Guardian Agent - Quick Rebuild"
echo "======================================"
echo ""

# Step 1: Remove old installation
echo "🗑️ Step 1: Removing old installation..."
sudo dpkg -r lab-guardian-agent 2>/dev/null || echo "   (No old installation found)"
sudo rm -rf /opt/lab-guardian 2>/dev/null || true

# Step 2: Clean build directory
echo "🧹 Step 2: Cleaning build directory..."
rm -rf build/deb

# Step 3: Rebuild the package
echo "📦 Step 3: Building new package..."
bash build_deb.sh

# Step 4: Install the new package
echo ""
echo "📥 Step 4: Installing new package..."
sudo dpkg -i build/deb/lab-guardian-agent-2.0.0.deb
sudo apt-get install -f -y

# Step 5: Test
echo ""
echo "✅ Done! Testing installation..."
echo ""
echo "To start the agent, run:"
echo "   lab-guardian start"
echo ""
echo "Or from Applications menu: 'Lab Guardian Agent'"
echo ""
