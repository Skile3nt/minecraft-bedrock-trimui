#!/usr/bin/env python3
"""Focused regression checks for the launcher-to-session profile handoff."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
menu = (root / 'portmaster/minecraftbedrock/minecraftbedrock/menu/main.lua').read_text()
entry = (root / 'portmaster/minecraftbedrock/Minecraft Bedrock.sh').read_text()
session = (root / 'crossmix/session.sh').read_text()
profiles = (root / 'crossmix/performance_profiles.py').read_text()
settings_entry = (root / 'portmaster/minecraftbedrock/Minecraft Bedrock.sh').read_text()

for value, label in [('ORIGINAL', 'Original'), ('NO_PARTICLES', 'No Particles'),
                     ('PERFORMANCE', 'Performance')]:
    assert f'{value} = "{label}"' in menu
    assert value in menu and value in entry
assert '"Left/Right or A: select; Play starts this profile"' in menu
assert 'adjustGameProfile(-1)' in menu and 'adjustGameProfile(1)' in menu
assert 'launching.profile = selectedGameProfile' not in menu  # stored at launch creation
assert 'profile = selectedGameProfile' in menu
assert '"play\\n" .. launching.name .. "\\n" .. launching.profile' in menu
assert 'menu_profile="$(sed -n 3p "$CONFDIR/menu_action.txt"' in entry
assert 'ORIGINAL|NO_PARTICLES|PERFORMANCE) export MCPE_PERF_PROFILE="$menu_profile"' in entry
assert 'performance_profile=${MCPE_PERF_PROFILE_ACTIVE:-ORIGINAL}' in session
assert "'PERFORMANCE'" in profiles and "[1024,576]" in profiles
assert "settings.get('texture_dequeue')" in profiles
assert 'key = "performance_fps_cap"' in menu
assert 'values = {"30", "40", "50"}' in menu
assert 'performance_fps_cap)' in settings_entry and 'MCPE_PERF_FPS_CAP' in settings_entry
assert "os.environ.get('MCPE_PERF_FPS_CAP'" in profiles
assert "failsafe_rung in ('','0')" in profiles
print('launcher profile selector/protocol/session checks passed')
