#!/usr/bin/env python3
"""Offline source audit. Uses only the Python standard library; imports no project code."""
import argparse
import ast
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {'.git', 'build', 'install', 'log', '__pycache__', '.venv', 'venv', 'reference'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', type=Path, help='Write a relative-path JSON audit report.')
    parser.add_argument('--verify-assets', action='store_true', help='Also hash local LFS asset contents.')
    args = parser.parse_args()
    errors = []
    counts = {'python': 0, 'package_xml': 0, 'urdf': 0, 'entry_points': 0,
              'cmake_installed_programs': 0, 'cuda_sources': 0, 'assets': 0}

    def fail(path, detail, line=None):
        errors.append({'path': path.relative_to(ROOT).as_posix(), 'line': line, 'detail': detail})

    for path in sorted(ROOT.rglob('*')):
        rel = path.relative_to(ROOT)
        if not path.is_file() or set(rel.parts) & SKIP:
            continue
        if path.suffix == '.py':
            counts['python'] += 1
            try:
                tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(rel))
            except (SyntaxError, UnicodeError) as exc:
                fail(path, str(getattr(exc, 'msg', exc)), getattr(exc, 'lineno', None))
                continue
            if path.name == 'setup.py':
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                        continue
                    if node.func.id == 'setup':
                        package_dir = {}
                        for kw in node.keywords:
                            if kw.arg == 'package_dir':
                                try: package_dir = ast.literal_eval(kw.value)
                                except (ValueError, TypeError): pass
                        for kw in node.keywords:
                            if kw.arg != 'entry_points': continue
                            try: entries = ast.literal_eval(kw.value)
                            except (ValueError, TypeError): continue
                            for entry in entries.get('console_scripts', []):
                                module = entry.split('=', 1)[1].strip().split(':', 1)[0]
                                prefixes = [p for p in package_dir if not p or module == p or module.startswith(p+'.')]
                                prefix = max(prefixes, key=len) if prefixes else ''
                                remainder = module[len(prefix):].lstrip('.') if prefix else module
                                base = path.parent / package_dir.get(prefix, '')
                                target = base.joinpath(*remainder.split('.'))
                                counts['entry_points'] += 1
                                if not target.with_suffix('.py').is_file() and not (target/'__init__.py').is_file():
                                    fail(path, 'Missing console-script module: '+module)
                    elif node.func.id == 'make_cuda_ext':
                        params = {kw.arg: kw.value for kw in node.keywords}
                        try:
                            module = ast.literal_eval(params['module'])
                            sources = ast.literal_eval(params['sources'])
                        except (KeyError, ValueError, TypeError): continue
                        for name in sources:
                            counts['cuda_sources'] += 1
                            target = path.parent.joinpath(*module.split('.'), name)
                            if not target.is_file(): fail(path, 'Missing CUDA extension source: '+str(target.relative_to(path.parent)))
        elif path.name == 'package.xml' or path.suffix == '.urdf':
            counts['package_xml' if path.name == 'package.xml' else 'urdf'] += 1
            try: ET.parse(path)
            except ET.ParseError as exc: fail(path, str(exc))
        elif path.name == 'CMakeLists.txt':
            text = path.read_text(encoding='utf-8-sig')
            for match in re.finditer(r'install\s*\(\s*PROGRAMS\s+(.*?)\s+DESTINATION', text, re.S):
                block = re.sub(r'#[^\n]*', '', match.group(1))
                for name in block.split():
                    name = name.strip('"')
                    if '$' in name or name.startswith('/'): continue
                    counts['cmake_installed_programs'] += 1
                    if not (path.parent/name).is_file(): fail(path, 'Missing install(PROGRAMS) input: '+name)

    if args.verify_assets:
        manifest = ROOT/'docs/assets_manifest.json'
        for row in json.loads(manifest.read_text(encoding='utf-8'))['assets']:
            path = ROOT/row['path']; counts['assets'] += 1
            if not path.is_file(): fail(path, 'Asset missing'); continue
            h = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''): h.update(chunk)
            if h.hexdigest() != row['sha256']: fail(path, 'Asset checksum mismatch; check LFS download or intentional replacement.')
    report = {'scope': 'Static syntax and declared-file existence only. Not a ROS build or hardware test.',
              'counts': counts, 'errors': errors, 'passed': not errors}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
