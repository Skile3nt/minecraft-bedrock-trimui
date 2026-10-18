#!/usr/bin/env python3
"""Guided physical gamepad capture, using CrossMix's existing status viewer.

No keyboard sampling, grabs, injection or mapping changes. Each named prompt
records the actual evdev codes, so printed button labels need not be guessed.
"""
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import time

EVENT = struct.Struct('@llHHi')
PROMPTS = ['A', 'B', 'X', 'Y', 'L1', 'R1', 'L2', 'R2', 'START', 'SELECT',
           'DPAD UP', 'DPAD DOWN', 'DPAD LEFT', 'DPAD RIGHT', 'LEFT STICK', 'RIGHT STICK']


def find_pad(text):
    for block in text.split('\n\n'):
        if 'N: Name="TRIMUI Player1"' not in block: continue
        ids = re.search(r'I: Bus=0003 Vendor=045e Product=028e Version=0114', block)
        node = re.search(r'\b(event\d+)\b', block)
        if ids and node: return '/dev/input/'+node.group(1), block
    raise RuntimeError('Verified built-in TrimUI gamepad not found')


def main():
    card = Path(os.environ['MCPE_CARD_ROOT']); game = Path(os.environ['GAMEDIR'])
    node, identity = find_pad(Path('/proc/bus/input/devices').read_text())
    viewer = card/'System/bin/sdl2imgshow'
    resources = card/'System/resources'
    if not viewer.is_file(): raise RuntimeError('CrossMix status viewer missing')
    fd = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
    axis_info = {}
    for code in (2, 5):
        try:
            raw = fcntl.ioctl(fd, 0x80184540+code, bytes(24))
            axis_info[str(code)] = dict(zip(['value','minimum','maximum','fuzz','flat','resolution'], struct.unpack('6i',raw)))
        except OSError: axis_info[str(code)] = {'available':False}
    viewer_log = (game/'logs/crossmix-input-viewer.log').open('w')
    observations = []; completed = False; process = None
    try:
        prompts = PROMPTS if os.environ.get('MCPE_INPUT_TEST_MODE') == 'full' else ['L2', 'R2']
        for label in prompts:
            # Drain only this diagnostic reader, never consume another process's events.
            while select.select([fd], [], [], 0)[0]: os.read(fd, EVENT.size*64)
            text = 'INPUT TEST: '+label+'\n'
            text += ('Move apenas este analogico em todas as direcoes.' if 'STICK' in label
                     else 'Pressione e solte apenas este botao.')
            process = subprocess.Popen([str(viewer), '-i', str(resources/'background.png'),
                '-f', str(resources/'DejaVuSans.ttf'), '-s', '28', '-c', '0,0,0', '-t', text],
                stdout=viewer_log, stderr=viewer_log)
            time.sleep(.2)
            if process.poll() is not None and process.returncode:
                raise RuntimeError('Native input prompt viewer failed: '+str(process.returncode))
            records = []; deadline = time.monotonic()+8; last_press = None
            while time.monotonic()<deadline:
                if select.select([fd], [], [], .1)[0]:
                    data = os.read(fd, EVENT.size*64)
                    for pos in range(0, len(data)-EVENT.size+1, EVENT.size):
                        _, _, kind, code, value = EVENT.unpack_from(data, pos)
                        if (kind == 1 and code >= 288) or kind == 3:
                            if len(records)<256: records.append({'type':kind, 'code':code, 'value':value})
                            if value and last_press is None: last_press=time.monotonic()
                # Allow a full stick excursion/trigger press and release before advancing.
                if last_press is not None and time.monotonic()-last_press>2: break
            observations.append({'physical_label':label, 'events':records, 'responded':bool(records)})
            process.terminate()
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: process.kill();process.wait(timeout=1)
            process = None;time.sleep(.3)
        completed = True
    finally:
        if process is not None:
            process.terminate()
            try: process.wait(timeout=1)
            except subprocess.TimeoutExpired: process.kill();process.wait(timeout=1)
        os.close(fd)
        viewer_log.close()
        report = {'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'device':node, 'identity':identity, 'completed':completed,
                  'observations':observations, 'axis_info':axis_info, 'mapping_modified':False,
                  'target':'built-in evdev gamepad',
                  'note':'Physical labels depend on following each prompt; review before changing mappings. Captures alone do not validate Minecraft input.'}
        path = game/'logs/crossmix-input-test.json'
        path.write_text(json.dumps(report, indent=2)+'\n')
        print('input_capture='+str(path)+' completed='+str(completed))


if __name__=='__main__': main()
