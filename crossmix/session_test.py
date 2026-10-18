#!/usr/bin/env python3
"""Reproduce missing X11 parent and distinguish Weston/probe/client failures.

Uses real Unix sockets with mock processes on the PC; never claims GPU validation.
The helper path is redirected at the Python execution boundary, leaving PC IPC
directories and the production session code unchanged.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import json
import time
import tempfile
import unittest

C = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prepare_x11', C/'prepare_x11.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class DirectoryTests(unittest.TestCase):
    def test_missing_directory_and_real_socket(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp)/'.X11-unix'
            with socket.socket(socket.AF_UNIX) as server:
                with self.assertRaises(FileNotFoundError):
                    server.bind(str(path/'X0'))
            old = os.umask(0o077)
            try:
                helper.prepare(path)
            finally:
                os.umask(old)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o1777)
            with socket.socket(socket.AF_UNIX) as server:
                server.bind(str(path/'X0'))
                helper.prepare(path)
                self.assertTrue((path/'X0').is_socket())

    def test_existing_directory_preserved(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp)/'.X11-unix'; path.mkdir(mode=0o755)
            marker = path/'existing'; marker.write_text('preserve')
            helper.prepare(path)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o755)
            self.assertEqual(marker.read_text(), 'preserve')

    def test_non_directory_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); path = tmp/'file'; path.touch()
            with self.assertRaises(RuntimeError): helper.prepare(path)
            link = tmp/'link'; link.symlink_to(tmp, target_is_directory=True)
            with self.assertRaises(RuntimeError): helper.prepare(link)

    def test_unsafe_existing_directory_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'.X11-unix'; path.mkdir(); path.chmod(0o777)
            with self.assertRaises(RuntimeError): helper.prepare(path)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o777)


class SessionTests(unittest.TestCase):
    def run_session(self, *, weston_status=0, probe_status=0, client_status=0, previous=False, close_pipe=False, signal_parent=False, performance=None, resolution_status=0, performance_fps_cap=None, failsafe_rung=None, play_timestamp=None):
        with tempfile.TemporaryDirectory(prefix='mcpe-session-') as tmp:
            tmp = Path(tmp); g = tmp/'game'; adapter = g/'crossmix'
            (adapter/'runtime/weston').mkdir(parents=True); (g/'logs').mkdir()
            (g/'logs/crossmix-session-report.json').write_text('{"old_stale_report":true}')
            for name in ('session.sh', 'prepare_x11.py', 'session_report.py'):
                shutil.copyfile(C/name, adapter/name)
            if performance:
                shutil.copyfile(C/'performance_profiles.py',adapter/'performance_profiles.py')
                version='1.16.221.01-971622101-arm64'
                data=g/'profiles'/version
                opt=data/'mcpelauncher/games/com.mojang/minecraftpe/options.txt';opt.parent.mkdir(parents=True)
                initial_cap='20' if failsafe_rung not in (None,0,'0') else '30'
                opt.write_text(f'gfx_fancygraphics:1\ngfx_bubble_particles:1\ngfx_max_framerate:{initial_cap}\n')
                particle=g/'versions'/version/'assets/resource_packs/vanilla/particles/a.json';particle.parent.mkdir(parents=True)
                particle.write_text(json.dumps({'format_version':'1.10.0','particle_effect':{'description':{'identifier':'minecraft:fixture'},'components':{'minecraft:emitter_rate_instant':{'num_particles':1}}}}))
            if previous:
                (adapter/'session.sh').write_bytes(subprocess.check_output(
                    ['git', 'show', '1c20976:crossmix/session.sh'], cwd=C))
            bindir = tmp/'bin'; bindir.mkdir()
            py = bindir/'python3'
            py.write_text('#!'+sys.executable+'\nimport os,sys\n'
                'args=sys.argv[1:]\n'
                'if args and args[0].endswith("/prepare_x11.py"):args.append(os.environ["FIXTURE_X11"])\n'
                'os.execv(sys.executable,[sys.executable,*args])\n')
            py.chmod(0o755)
            (adapter/'probe.py').write_text(
                f'import sys\nsys.exit({probe_status})\n' if probe_status else
                'print("CRUSTY_LIBSDL=/fixture/sdl\\nCRUSTY_LIBEGL=/fixture/egl\\nCRUSTY_LIBGLES=/fixture/gles")\n')
            run = adapter/'native-run.sh'
            run.write_text('''#!'''+sys.executable+'''
import os,socket,sys,time
from pathlib import Path
if Path(sys.argv[1]).name=='wp_weston':
 if int(os.environ['FIXTURE_WESTON_STATUS']):sys.exit(int(os.environ['FIXTURE_WESTON_STATUS']))
 x=socket.socket(socket.AF_UNIX)
 try:x.bind(os.environ['FIXTURE_X11']+'/X42')
 except FileNotFoundError:
  print('failed to bind to X42: No such file or directory',flush=True);sys.exit(23)
 w=socket.socket(socket.AF_UNIX);w.bind(os.environ['XDG_RUNTIME_DIR']+'/mcpe-wayland')
 print('xserver listening on display :42',flush=True)
 while True:time.sleep(.05)
elif Path(sys.argv[1]).name=='sdl-session-probe':
 sys.exit(int(os.environ['FIXTURE_RESOLUTION_STATUS']))
else:
 Path(os.environ['GAMEDIR']+'/client-was-started').touch()
 Path(os.environ['GAMEDIR']+'/render-record').write_text(os.environ['MCPE_RENDER_WIDTH']+'x'+os.environ['MCPE_RENDER_HEIGHT'])
 option=Path(os.environ['MCPELAUNCHER_DATA_DIR'])/'games/com.mojang/minecraftpe/options.txt'
 Path(os.environ['GAMEDIR']+'/fps-option-at-run').write_text(option.read_text() if option.exists() else 'missing')
 if 'MCPE_BENCH_FILE' in os.environ:
  frame_path=Path(os.environ['MCPE_BENCH_FILE'])
  assert frame_path.parent.name.startswith('mcpe-crossmix.'), frame_path
  frame_path.write_text('{"fixture":"frame batch"}\\n')
 if os.environ['FIXTURE_SLEEP']=='1':time.sleep(10)
 sys.exit(int(os.environ['FIXTURE_CLIENT_STATUS']))
'''); run.chmod(0o755)
            env = dict(os.environ, GAMEDIR=str(g), MCVER_OVERRIDE='fixture', MCPE_CARD_ROOT=str(tmp),
                PATH=str(bindir)+os.pathsep+os.environ['PATH'], FIXTURE_X11=str(tmp/'.X11-unix'),
                FIXTURE_WESTON_STATUS=str(weston_status), FIXTURE_CLIENT_STATUS=str(client_status),
                FIXTURE_SLEEP='1' if signal_parent else '0')
            env['FIXTURE_RESOLUTION_STATUS']=str(resolution_status)
            if performance:
                env.update(MCVER_OVERRIDE=version,MCPE_DATA_ROOT_OVERRIDE=str(data),MCPE_PERF_PROFILE=performance)
            if performance_fps_cap is not None:
                env['MCPE_PERF_FPS_CAP']=str(performance_fps_cap)
            if failsafe_rung is not None:
                env['MCPE_FAILSAFE_RUNG']=str(failsafe_rung)
            if play_timestamp is not None:
                (g/'config').mkdir(exist_ok=True)
                uptime=float(Path('/proc/uptime').read_text().split()[0])
                stamp=uptime if play_timestamp=='valid' else uptime+10000
                (g/'config/play-uptime.txt').write_text(f'{stamp:.2f}\n')
                env['MCPE_BOOT_UPTIME']=str(int(uptime)-1)
            if close_pipe or signal_parent:
                p = subprocess.Popen(['bash', str(adapter/'session.sh')], env=env,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                p.stdout.close()
                if signal_parent:
                    deadline=time.monotonic()+3
                    while not (g/'client-was-started').exists() and time.monotonic()<deadline:time.sleep(.02)
                    self.assertTrue((g/'client-was-started').exists())
                    time.sleep(.1);p.terminate()
                p.wait(timeout=12)
            else:
                p = subprocess.run(['bash', str(adapter/'session.sh')], env=env,
                    text=True, capture_output=True, timeout=12)
            logs = '\n'.join(f.read_text() for f in (g/'logs').glob('*.log'))
            if not previous:
                report=json.loads((g/'logs/crossmix-session-report.json').read_text())
                self.assertNotIn('old_stale_report',report)
                self.assertEqual(report['exit_code'],p.returncode)
                self.assertEqual(report['state'],'finished')
                self.assertTrue(any(e['event']=='session_cleanup_finished' for e in report['timing_events']))
                if play_timestamp is not None:
                    found=any(e['event']=='play_selected' for e in report['timing_events'])
                    self.assertEqual(found,play_timestamp=='valid')
                if signal_parent:
                    self.assertEqual(report['failed_component'],'external-session-signal')
            started = (g/'client-was-started').exists()
            if not previous and started:
                self.assertEqual((g/'logs/crossmix-frames.jsonl').read_text(),
                                 '{"fixture":"frame batch"}\n')
                self.assertIn('frame_metrics_sink=tmpfs', logs)
                self.assertIn('frame_metrics_persisted=1 sink=tmpfs', logs)
            if performance:
                expected='1024x576' if performance=='PERFORMANCE' and resolution_status==0 else '1280x720'
                self.assertEqual((g/'render-record').read_text(),expected)
                if performance=='PERFORMANCE':
                    cap=performance_fps_cap or 30
                    if failsafe_rung not in (None,0,'0'):
                        cap=20
                        self.assertIn('performance_fps_cap_requested=failsafe-managed',logs)
                    else:
                        self.assertIn(f'performance_fps_cap_requested={cap} option=gfx_max_framerate scope=temporary-profile',logs)
                    self.assertIn(f'performance_fps_cap_option_at_exit={cap}',logs)
                    self.assertIn(f'gfx_max_framerate:{cap}',(g/'fps-option-at-run').read_text())
                restored_cap='20' if failsafe_rung not in (None,0,'0') else '30'
                self.assertEqual(opt.read_text(),f'gfx_fancygraphics:1\ngfx_bubble_particles:1\ngfx_max_framerate:{restored_cap}\n')
                self.assertFalse((g/'config/performance-018-state.json').exists())
            return p.returncode, logs, started

    def test_play_timestamp_valid_and_previous_boot_rejected(self):
        for value in ('valid','future'):
            with self.subTest(timestamp=value):
                code,logs,started=self.run_session(play_timestamp=value)
                self.assertEqual(code,0,logs);self.assertTrue(started)

    def test_original_missing_parent_reproduced_and_fixed(self):
        code, logs, started = self.run_session(previous=True)
        self.assertEqual(code, 1); self.assertFalse(started)
        self.assertIn('No such file or directory', logs)
        code, logs, started = self.run_session()
        self.assertEqual(code, 0, logs); self.assertTrue(started)
        self.assertIn('created=1 mode=1777', logs)

    def test_weston_failure_identified(self):
        code, logs, started = self.run_session(weston_status=23)
        self.assertEqual(code, 1); self.assertFalse(started)
        self.assertIn('process=weston exit_code=23 client_started=0', logs)

    def test_probe_failure_not_hidden_by_eval(self):
        code, logs, started = self.run_session(probe_status=7)
        self.assertEqual(code, 7); self.assertFalse(started)
        self.assertIn('stage=native-libraries', logs)
        self.assertIn('exit_code=7', logs)

    def test_client_exit_code_preserved(self):
        code, logs, started = self.run_session(client_status=42)
        self.assertEqual(code, 42); self.assertTrue(started)
        self.assertIn('process=mcpelauncher-client exit_code=42', logs)

    def test_closed_stdout_does_not_replace_original_status(self):
        code, logs, started=self.run_session(client_status=42,close_pipe=True)
        self.assertEqual(code,42,logs);self.assertTrue(started)
        self.assertNotIn('session_report_failed',logs)

    def test_external_term_reported_and_children_cleaned(self):
        code, logs, started=self.run_session(signal_parent=True)
        self.assertEqual(code,143,logs);self.assertTrue(started)
        self.assertIn('session_signal=TERM',logs)
        self.assertNotIn('session_report_failed',logs)

    def test_performance_profile_restore_and_surface_gate(self):
        for code in (0,3):
            status,logs,started=self.run_session(performance='PERFORMANCE',resolution_status=code)
            self.assertEqual(status,0,logs);self.assertTrue(started)
            self.assertIn('reduced_resolution_rejected' if code else 'reduced_resolution_surface_verified',logs)

    def test_performance_cap_ab_values_reach_the_client_then_restore(self):
        for cap in (40,50):
            with self.subTest(cap=cap):
                status,logs,started=self.run_session(performance='PERFORMANCE',performance_fps_cap=cap)
                self.assertEqual(status,0,logs);self.assertTrue(started)

    def test_performance_fps_experiment_never_overrides_failsafe(self):
        status,logs,started=self.run_session(performance='PERFORMANCE',performance_fps_cap=50,failsafe_rung=2)
        self.assertEqual(status,0,logs);self.assertTrue(started)

    def test_original_profile_preserves_reference(self):
        status,logs,started=self.run_session(performance='ORIGINAL')
        self.assertEqual(status,0,logs);self.assertTrue(started)


if __name__ == '__main__': unittest.main()
