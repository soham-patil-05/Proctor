# Process Tracking Improvements

## Changes Made

### ✅ Unique Process Tracking

**Before:**
- Chrome would appear multiple times if there were multiple Chrome windows
- Same process could be logged repeatedly

**After:**
- Each unique process is logged **only once**
- If Chrome is already displayed, it won't be displayed again
- Multiple instances shown as count: `Chrome (x3)`

---

### ✅ Separate Incognito/Private Tracking

**Before:**
- Chrome and Chrome Incognito were mixed together
- No distinction between normal and private browsing

**After:**
- **Chrome** and **Chrome Incognito** are treated as **SEPARATE processes**
- **Firefox** and **Firefox Private** are treated as **SEPARATE processes**
- Each appears independently in the list

#### Display Format:

| Process Name | Description |
|-------------|-------------|
| `Chrome` | Normal Chrome browser |
| `Chrome 🔒 (Incognito)` | Chrome in incognito mode |
| `Chrome (x2)` | Two normal Chrome instances |
| `Firefox` | Normal Firefox browser |
| `Firefox 🔒 (Private Window)` | Firefox in private mode |
| `Edge 🔒 (Incognito)` | Edge in InPrivate mode |
| `Brave 🔒 (Incognito)` | Brave in private mode |

---

### ✅ Important Data Only

**What's Tracked:**
- ✅ Browser processes (Chrome, Firefox, Edge, Brave, Opera, Vivaldi)
- ✅ Terminal emulators (bash, zsh, PowerShell, cmd, etc.)
- ✅ Communication apps (Discord, Zoom, Teams, Skype, etc.)
- ✅ Remote access tools (AnyDesk, TeamViewer, etc.) - **HIGH RISK**
- ✅ IDEs and code editors (VS Code, Sublime, etc.)
- ✅ Unknown processes with notable CPU usage (>5%)

**What's Filtered Out:**
- ❌ System processes (systemd, kernel, services, etc.)
- ❌ Background daemons
- ❌ Low CPU usage unknown processes (<5%)
- ❌ Safe desktop environment processes

---

## How It Works

### 1. Process Detection (`process_monitor.py`)

```python
# Unique key combines process name + incognito status
key = f"{process_name}|incognito={is_incognito}"

# Chrome normal → key = "chrome|incognito=False"
# Chrome incognito → key = "chrome|incognito=True"
# These are treated as TWO DIFFERENT processes
```

### 2. Database Storage (`local_db.py`)

```sql
-- Checks for exact match including incognito status
SELECT id FROM local_processes 
WHERE session_id = ? 
  AND process_name = ? 
  AND is_incognito = ?

-- "Chrome" with is_incognito=0 is different from
-- "Chrome 🔒 (Incognito)" with is_incognito=1
```

### 3. UI Display (`agent_ui.py`)

```python
# Uses unique key to track what's already displayed
if key in self._seen_processes:
    continue  # Skip duplicates

self._seen_processes.add(key)
# Add to table...
```

---

## Risk Levels

| Level | Color | Examples |
|-------|-------|----------|
| **HIGH** | 🔴 Red | Incognito browsers, remote access tools, terminals |
| **MEDIUM** | 🟡 Yellow | Normal browsers, communication apps, IDEs |
| **LOW** | 🟢 Green | Unknown processes with notable CPU |

---

## Examples

### Scenario 1: Student opens Chrome
```
Process Table:
Count | Name        | Risk    | Status
------|-------------|---------|--------
1     | Chrome      | MEDIUM  | Running
```

### Scenario 2: Student opens Chrome Incognito
```
Process Table:
Count | Name                    | Risk | Status
------|-------------------------|------|--------
1     | Chrome                  | MEDIUM | Running
1     | Chrome 🔒 (Incognito)   | HIGH   | Running  ← NEW ENTRY
```

### Scenario 3: Student opens Firefox Private
```
Process Table:
Count | Name                        | Risk | Status
------|-----------------------------|------|--------
1     | Chrome                      | MEDIUM | Running
1     | Chrome 🔒 (Incognito)       | HIGH   | Running
1     | Firefox                     | MEDIUM | Running
1     | Firefox 🔒 (Private Window) | HIGH   | Running  ← NEW ENTRY
```

### Scenario 4: Student opens 3 Chrome windows
```
Process Table:
Count | Name                        | Risk | Status
------|-----------------------------|------|--------
3     | Chrome (x3)                 | MEDIUM | Running  ← Updated count
1     | Chrome 🔒 (Incognito)       | HIGH   | Running
1     | Firefox                     | MEDIUM | Running
1     | Firefox 🔒 (Private Window) | HIGH   | Running
```

---

## Technical Details

### Incognito Detection Methods

**Chrome/Chromium:**
- Command line flags: `--incognito`, `--guest`
- Temp profile detection: `--user-data-dir` with temp path

**Firefox:**
- Command line flags: `-private`, `-private-window`, `--private-window`
- No-remote without profile: `-no-remote` without `-profile`
- New instance flag: `-new-instance`

**Edge:**
- Command line flags: `--inprivate`, `-inprivate`

**Brave/Opera/Vivaldi:**
- Similar to Chrome (Chromium-based)

---

## Benefits

1. **Clean Display** - No duplicate processes cluttering the UI
2. **Clear Privacy Violations** - Incognito/private windows immediately visible
3. **Accurate Tracking** - Each unique process logged exactly once
4. **Better Monitoring** - Teachers can see if students open private browsing
5. **Efficient Storage** - Database stores only unique process entries

---

## Testing

To test the changes:

```bash
# Start agent with verbose logging
cd Lab_guardian
python3 -m lab_guardian start -vv

# Watch the logs for:
# 🔍 BROWSER CHECK: name='firefox', is_browser=True, cmd=...
# 🔒 FIREFOX PRIVATE WINDOW DETECTED: firefox
# 🔒 INCOGNITO DETECTED: chrome with flag --incognito
```

---

## Files Modified

1. **`Lab_guardian/lab_guardian/monitor/process_monitor.py`**
   - Updated `_classify_process()` to add `is_incognito` flag to all processes
   - Improved labels for Firefox Private vs Chrome Incognito

2. **`Lab_guardian/lab_guardian/local_db.py`**
   - Updated `insert_process_snapshot()` to use unique key `(name, is_incognito)`
   - Database checks for exact match including incognito status
   - Display names include browser-specific private mode indicators

3. **`Lab_guardian/lab_guardian/agent_ui.py`**
   - Updated `on_processes_update()` to use unique key `(name, is_incognito)`
   - Removed duplicate incognito appending logic (now handled in database)

---

## Summary

✅ **Chrome ≠ Chrome Incognito** (separate entries)  
✅ **Firefox ≠ Firefox Private** (separate entries)  
✅ **No duplicate processes** (each unique process shown once)  
✅ **Clear visual indicators** (🔒 icon + specific labels)  
✅ **High risk for private modes** (immediate flagging)  
✅ **Efficient storage** (only unique entries in database)
