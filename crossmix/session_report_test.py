#!/usr/bin/env python3
import tempfile
from pathlib import Path
import unittest
from session_report import summarize


class ReportTests(unittest.TestCase):
    def fixture(self, client, weston='', session='process=mcpelauncher-client pid=42\n', status=1, stage='client-finished'):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            for name,data in [('client',client),('weston',weston),('session',session)]:
                (p/f'crossmix-{name}.log').write_text(data)
            return summarize(p,status,stage)

    def test_observed_first_error_and_fatal(self):
        p=self.fixture('linker loaded\nNo current EGL context or display.\n'
            'SDL_EGL_CreateSurface fail: no config\nFailed to load host libfmod\nEGLUT: failed to choose a config\n',
            "xserver listening on display :0\nlaunching 'xwayland.sh'\ncreated wm, root 80\n")
        self.assertEqual(p['failed_process'],'mcpelauncher-client')
        self.assertEqual(p['first_error'],'No current EGL context or display.')
        self.assertEqual(p['first_fatal'],'SDL_EGL_CreateSurface fail: no config')
        self.assertTrue(p['weston_listening'] and p['xwayland_wm_ready'])
        self.assertFalse(p['minecraft_library_loaded_seen'])

    def test_loader_failure(self):
        p=self.fixture('app: error while loading shared libraries: missing.so\n')
        self.assertEqual(p['failed_component'],'dynamic-loader')

    def test_targeted_trace_and_probe_identity(self):
        p=self.fixture('CrossMix native_SDL_version=2.26.5\n'
            'CrossMix graphics_end step=SDL_Init result=0 driver=mali\n'
            'CrossMix binding symbol=eglChooseConfig caller=SDL provider=Crusty lookup=dlsym\n'
            'CrossMix graphics_failure step=SDL_CreateWindow SDL_GetError=window surface failed\n'
            'CrossMix graphics_failure step=SDL_GL_CreateContext SDL_GetError=Invalid window\n',
            session='process=sdl-session-probe pid=42\nprocess_state_at_client_end weston_alive=1 xwayland_alive=0\n')
        self.assertEqual(p['failed_process'],'sdl-session-probe')
        self.assertEqual(p['graphics_failed_step'],'SDL_CreateWindow')
        self.assertEqual(p['sdl_error'],'window surface failed')
        self.assertEqual(p['sdl_version'],'2.26.5')
        self.assertEqual(p['sdl_video_driver'],'mali')
        self.assertEqual(p['screen_message'],'SDL_CreateWindow failed')
        self.assertTrue(p['weston_alive_at_client_end'])
        self.assertFalse(p['xwayland_alive_at_client_end'])
        self.assertEqual(len(p['graphics_bindings']),1)

    def test_unknown_process_state_and_ansi_preserved_in_original(self):
        p=self.fixture('\x1b[?25hNo current EGL context or display.\n')
        self.assertEqual(p['first_error'],'No current EGL context or display.')
        self.assertIsNone(p['weston_alive_at_client_end'])
        self.assertIsNone(p['xwayland_alive_at_client_end'])

    def test_minecraft_loader_failure(self):
        p=self.fixture('Loading Minecraft library\nFailed to load Minecraft library\n',status=51)
        self.assertTrue(p['minecraft_library_loading_seen'])
        self.assertEqual(p['failed_component'],'android-game-loader')

    def test_success_does_not_claim_gameplay(self):
        p=self.fixture('Loaded Minecraft library\n',status=0)
        self.assertIsNone(p['failed_process'])
        self.assertIn('unconfirmed',p['minecraft_execution'])
        self.assertFalse(p['world_loaded_seen'])

    def test_world_connection_marker_is_boolean_and_does_not_log_identity(self):
        p=self.fixture('Player connected: Steve, xuid: private-value\n',status=6)
        self.assertTrue(p['world_loaded_seen'])
        self.assertNotIn('private-value',str(p))

    def test_weston_failure(self):
        p=self.fixture('client_not_started', 'failed to bind: missing parent\n',session='',stage='weston-start')
        self.assertEqual(p['failed_process'],'weston')
        self.assertIn('failed to bind',p['first_error'])
        self.assertFalse(p['client_spawned'])

    def test_interruption_after_minecraft_started_not_graphics_failure(self):
        p=self.fixture('Loaded Minecraft library\nInvoking ANativeActivity_onCreate\nX connection to :0 broken\n',
            session='process=mcpelauncher-client pid=42\nsession_signal=TERM stage=client-wait\n'
                    'cleanup=stopping owned client/Weston\nsession_signal=HUP\n',status=143)
        self.assertEqual(p['failed_component'],'external-session-signal')
        self.assertEqual(p['session_signal'],'TERM')
        self.assertTrue(p['android_activity_started'])
        self.assertFalse(p['activity_stop_requested'])

    def test_shutdown_timeout_not_startup_graphics_failure(self):
        p=self.fixture('Loaded Minecraft library\nInvoking stop activity callbacks\nshutdown_grace_exceeded=15s\n',status=137)
        self.assertEqual(p['failed_component'],'shutdown-timeout')
        self.assertTrue(p['activity_stop_requested'])
        self.assertTrue(p['shutdown_watchdog_triggered'])

    def test_x_connection_lost_does_not_imply_gpu_failure(self):
        p=self.fixture('Loaded Minecraft library\nX connection to :0 broken\n')
        self.assertEqual(p['failed_component'],'xwayland-connection-lost')

    def test_cleanup_messages_cannot_become_startup_failure(self):
        p=self.fixture('Loaded Minecraft library\nCrossMix cleanup_begin\n'
                       'CrossMix graphics_failure step=SDL_CreateWindow SDL_GetError=teardown\n',status=0)
        self.assertIsNone(p['first_fatal'])
        self.assertIsNone(p['graphics_failed_step'])


if __name__=='__main__':unittest.main()
