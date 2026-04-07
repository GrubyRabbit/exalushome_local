#!/usr/bin/env python3

"""
Phase 1: Download and extract npm packages for inspection

Usage:
    python3 scripts/unpack_packages.py

Downloads key packages from npm registry and extracts them to /tmp/exalushome_packages
for offline analysis.
"""

import json
import subprocess
import os
import sys
import tarfile
import urllib.request
import tempfile
from pathlib import Path

# Key packages to inspect
PACKAGES = [
    'lavva.exalushome',
    'lavva.exalushome.portos',
    'lavva.exalushome.network',
    'lavva.exalushome.extalife',
    'exalushome-wekta',
]

EXTRACT_DIR = Path('/tmp/exalushome_packages')
ARTIFACTS_DIR = Path(__file__).parent.parent / 'artifacts'

EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

print(f'[*] Extracting packages to: {EXTRACT_DIR}\n')

package_versions = {}

for pkg in PACKAGES:
    print(f'[+] Processing package: {pkg}')
    
    try:
        # Fetch package info from npm registry
        registry_url = f'https://registry.npmjs.org/{pkg}'
        with urllib.request.urlopen(registry_url) as response:
            npm_info = json.loads(response.read().decode('utf-8'))
        
        version = npm_info.get('dist-tags', {}).get('latest')
        if not version:
            print(f'    ✗ Could not find latest version\n')
            continue
        
        pkg_data = npm_info.get('versions', {}).get(version, {})
        tarball = pkg_data.get('dist', {}).get('tarball')
        
        if not tarball:
            print(f'    ✗ Could not find tarball URL\n')
            continue
        
        print(f'    Version: {version}')
        print(f'    Tarball: {tarball}')
        
        package_versions[pkg] = {
            'version': version,
            'tarball': tarball,
            'description': npm_info.get('description', ''),
            'main': pkg_data.get('main', ''),
            'exports': pkg_data.get('exports', {}),
            'dependencies': pkg_data.get('dependencies', {}),
        }
        
        # Download and extract
        pkg_dir = EXTRACT_DIR / pkg.replace('.', '_')
        pkg_dir.mkdir(parents=True, exist_ok=True)
        
        print(f'    Downloading and extracting...')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz') as tmp:
            tmp_path = tmp.name
        
        try:
            # Download tarball
            urllib.request.urlretrieve(tarball, tmp_path)
            
            # Extract
            with tarfile.open(tmp_path, 'r:gz') as tar:
                tar.extractall(str(pkg_dir))
            
            print(f'    ✓ Extracted to {pkg_dir}\n')
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
    except Exception as err:
        print(f'    ✗ Error: {err}\n')

# Save package metadata
version_file = ARTIFACTS_DIR / 'package_versions.json'
with open(version_file, 'w') as f:
    json.dump(package_versions, f, indent=2)

print(f'[✓] Saved package metadata to: {version_file}')

# Generate file tree listing
print(f'\n[*] Generating file tree listings...')
for pkg in PACKAGES:
    pkg_dir = EXTRACT_DIR / pkg.replace('.', '_')
    if pkg_dir.exists():
        try:
            result = subprocess.run(
                f'find "{pkg_dir}" -type f | head -100',
                shell=True,
                capture_output=True,
                text=True
            )
            
            tree_file = ARTIFACTS_DIR / f'tree_{pkg.replace(".", "_")}.txt'
            with open(tree_file, 'w') as f:
                f.write(result.stdout)
            
            print(f'    ✓ {pkg}')
        except Exception as err:
            print(f'    ✗ {pkg}: {err}')

print(f'\n[✓] Phase 1 complete: Packages extracted to {EXTRACT_DIR}')
print(f'\nNext: Run "python3 scripts/inspect_exports.py" to analyze exports')
