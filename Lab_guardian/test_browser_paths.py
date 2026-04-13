#!/usr/bin/env python3
"""Test script to check if browser history databases exist on Ubuntu."""

import os
from glob import glob

# Common browser history paths on Linux
browser_paths = {
    'Google Chrome': '~/.config/google-chrome/Default/History',
    'Chromium': '~/.config/chromium/Default/History',
    'Chromium (Snap)': '~/snap/chromium/common/chromium/Default/History',
    'Brave': '~/.config/BraveSoftware/Brave-Browser/Default/History',
    'Brave (Snap)': '~/snap/brave/common/.config/BraveSoftware/Brave-Browser/Default/History',
    'Microsoft Edge': '~/.config/microsoft-edge/Default/History',
    'Firefox': '~/.mozilla/firefox/*/places.sqlite',
    'Firefox (Snap)': '~/snap/firefox/common/.mozilla/firefox/*/places.sqlite',
}

print("Checking browser history database locations...\n")

found_any = False
for browser_name, path_template in browser_paths.items():
    path = os.path.expanduser(path_template)
    
    if '*' in path:
        matches = glob(path)
        if matches:
            found_any = True
            print(f"✅ {browser_name}:")
            for match in matches:
                size = os.path.getsize(match) if os.path.exists(match) else 0
                print(f"   {match} ({size / 1024 / 1024:.2f} MB)")
        else:
            print(f"❌ {browser_name}: Not found")
    else:
        if os.path.exists(path):
            found_any = True
            size = os.path.getsize(path)
            print(f"✅ {browser_name}:")
            print(f"   {path} ({size / 1024 / 1024:.2f} MB)")
        else:
            print(f"❌ {browser_name}: Not found")

print()
if found_any:
    print("Found at least one browser history database!")
else:
    print("No browser history databases found.")
    print("\nPossible reasons:")
    print("1. Browsers are not installed")
    print("2. Browsers have never been used (no history yet)")
    print("3. Using a different profile location")
    print("\nTry running these commands to find browsers:")
    print("  which google-chrome chromium chromium-browser firefox brave microsoft-edge")
    print("  ls -la ~/.config/")
    print("  ls -la ~/.mozilla/")
