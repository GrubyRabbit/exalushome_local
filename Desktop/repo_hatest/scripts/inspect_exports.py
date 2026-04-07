#!/usr/bin/env python3

"""
Phase 2: Analyze exported classes, functions, types from extracted packages

Usage:
    python3 scripts/inspect_exports.py

Scans package files for:
- exported classes and functions
- keywords: login, auth, token, local, ip, host, websocket, shutter, position, state, command
- transport abstractions
- type definitions

Outputs analysis to /artifacts/exports_analysis.json
"""

import json
import re
from pathlib import Path
from collections import defaultdict

EXTRACT_DIR = Path('/tmp/exalushome_packages')
ARTIFACTS_DIR = Path(__file__).parent.parent / 'artifacts'

# Search patterns for important concepts
PATTERNS = {
    'auth': r'\b(login|logout|auth|authenticate|token|jwt|bearer|refresh|session)\b',
    'local': r'\b(local|ip|host|port|localhost|127\.0\.0\.1|192\.168|10\.0|direct|lan|lan-mode|controller)\b',
    'remote': r'\b(remote|cloud|api|endpoint|server|https?:|websocket|mqtt|ws:)\b',
    'shutter': r'\b(shutter|blind|cover|roller|curtain|portos)\b',
    'position': r'\b(position|level|percent|percentage|open|close|state|status|angle)\b',
    'transport': r'\b(http|websocket|mqtt|tcp|udp|protocol|request|response|client|server)\b',
    'device': r'\b(device|entity|asset|thing|resource|object|id|uid|mac|serial)\b',
}

analysis = {
    'packages': {},
    'summary': {
        'totalFiles': 0,
        'filesWithAuth': [],
        'filesWithLocal': [],
        'filesWithRemote': [],
        'filesWithShutter': [],
        'filesWithPosition': [],
        'filesWithTransport': [],
    },
}

def analyze_file(filepath, content, rel_path):
    """Analyze a single file for relevant patterns"""
    findings = {
        'filepath': str(rel_path),
        'size': len(content),
        'lines': len(content.split('\n')),
        'patterns': {},
    }
    
    has_pattern = False
    for key, pattern in PATTERNS.items():
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            # Deduplicate and convert to lowercase
            findings['patterns'][key] = sorted(set(m.lower() for m in matches))
            has_pattern = True
            
            if key == 'auth':
                analysis['summary']['filesWithAuth'].append(str(rel_path))
            if key == 'local':
                analysis['summary']['filesWithLocal'].append(str(rel_path))
            if key == 'remote':
                analysis['summary']['filesWithRemote'].append(str(rel_path))
            if key == 'shutter':
                analysis['summary']['filesWithShutter'].append(str(rel_path))
            if key == 'position':
                analysis['summary']['filesWithPosition'].append(str(rel_path))
            if key == 'transport':
                analysis['summary']['filesWithTransport'].append(str(rel_path))
    
    analysis['summary']['totalFiles'] += 1
    
    if has_pattern:
        pkg = rel_path.parts[0]
        if pkg not in analysis['packages']:
            analysis['packages'][pkg] = []
        analysis['packages'][pkg].append(findings)

def search_directory(dir_path, root_path):
    """Recursively search directory for relevant files"""
    try:
        for entry in dir_path.iterdir():
            # Skip certain directories
            if entry.name in ['node_modules', '.npm', 'dist', 'build', '.git', '.turbo', '.next']:
                continue
            
            if entry.is_dir():
                search_directory(entry, root_path)
            elif entry.is_file() and entry.name.endswith(('.js', '.ts', '.json')):
                try:
                    content = entry.read_text(encoding='utf-8', errors='ignore')
                    rel_path = entry.relative_to(root_path)
                    analyze_file(str(entry), content, rel_path)
                except Exception:
                    pass  # Skip unreadable files
    except Exception:
        pass

print('[*] Analyzing extracted packages...\n')

if EXTRACT_DIR.exists():
    for pkg_dir in sorted(EXTRACT_DIR.iterdir()):
        if pkg_dir.is_dir():
            print(f'[+] Analyzing {pkg_dir.name}...')
            search_directory(pkg_dir, pkg_dir)

# Save analysis
analysis_file = ARTIFACTS_DIR / 'exports_analysis.json'
with open(analysis_file, 'w') as f:
    json.dump(analysis, f, indent=2)

print(f'\n[✓] Analysis saved to: {analysis_file}\n')

# Print summary
print('=== ANALYSIS SUMMARY ===\n')
print(f'Total files scanned: {analysis["summary"]["totalFiles"]}')
print(f'Files with auth keywords: {len(analysis["summary"]["filesWithAuth"])}')
print(f'Files with local keywords: {len(analysis["summary"]["filesWithLocal"])}')
print(f'Files with remote keywords: {len(analysis["summary"]["filesWithRemote"])}')
print(f'Files with shutter keywords: {len(analysis["summary"]["filesWithShutter"])}')
print(f'Files with position keywords: {len(analysis["summary"]["filesWithPosition"])}')
print(f'Files with transport keywords: {len(analysis["summary"]["filesWithTransport"])}')

print(f'\nKey findings by package:\n')
for pkg in sorted(analysis['packages'].keys()):
    files = analysis['packages'][pkg]
    print(f'{pkg}: {len(files)} files with relevant patterns')
    if 0 < len(files) <= 5:
        for f in files[:5]:
            print(f'  - {f["filepath"]}')

print(f'\nNext: Review extracted packages in {EXTRACT_DIR} manually')
print(f'For detailed exploration and documentation writing')
