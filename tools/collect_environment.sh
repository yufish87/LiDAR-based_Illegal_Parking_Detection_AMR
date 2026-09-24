#!/usr/bin/env bash
# Read-only environment inventory. Does not start ROS nodes or control hardware.
set -u
printf 'UTC: '
date -u '+%Y-%m-%dT%H:%M:%SZ'
uname -a
if [ -r /etc/os-release ]; then cat /etc/os-release; fi
if [ -r /etc/nv_tegra_release ]; then cat /etc/nv_tegra_release; fi
printf '\nROS_DISTRO=%s\n' "${ROS_DISTRO:-unset}"
python3 --version
if command -v nvcc >/dev/null 2>&1; then nvcc --version; fi
python3 - <<'PY'
import importlib.metadata as metadata
import platform
print('machine:', platform.machine())
print('python:', platform.python_version())
for package in ['numpy', 'pyserial', 'torch', 'torchvision', 'spconv', 'spconv-cu113',
                'spconv-cu114', 'spconv-cu117', 'spconv-cu120', 'pcdet',
                'opencv-python', 'requests', 'PyYAML', 'PySide6', 'pyqtgraph']:
    try:
        print(package, metadata.version(package))
    except metadata.PackageNotFoundError:
        print(package, '(not installed under this distribution name)')
PY
if command -v dpkg-query >/dev/null 2>&1; then
  dpkg-query -W -f='${Package}\t${Version}\n' 'nvidia-jetpack' 'nvidia-l4t-core' 'ros-*-navigation2' 'ros-*-nav2-bringup' 2>/dev/null || true
fi
printf '\nReview this output and record the selected versions in docs before publishing a tested release.\n'
