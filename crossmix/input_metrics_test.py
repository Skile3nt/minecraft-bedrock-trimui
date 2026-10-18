#!/usr/bin/env python3
"""Host telemetry/parser regressions; synthetic input is never physical proof."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import session_metrics

C = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('input_test', C/'input-test.py')
capture = importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)


class Tests(unittest.TestCase):
    def test_exact_device_identity(self):
        text='I: Bus=0003 Vendor=045e Product=028e Version=0114\nN: Name="TRIMUI Player1"\nH: Handlers=js0 event3\n'
        self.assertEqual(capture.find_pad(text)[0],'/dev/input/event3')
        for bad in (text.replace('028e','0000'),text.replace('TRIMUI Player1','Keyboard')):
            with self.assertRaises(RuntimeError):capture.find_pad(bad)

    def test_read_proc_without_logging_commandline(self):
        fields=session_metrics.read_metrics(os.getpid())
        self.assertIn('VmRSS',fields);self.assertIn('cpu_ticks',fields)
        self.assertNotIn('cmdline',fields)
        self.assertTrue(session_metrics.read_metrics(2147483647)['exited_or_unreadable'])

    def test_missing_proc_io_does_not_mark_alive_process_exited(self):
        original=Path.read_text
        def read(path,*a,**kw):
            if path.name=='io':raise FileNotFoundError('kernel has no IO accounting')
            return original(path,*a,**kw)
        with patch.object(Path,'read_text',read):data=session_metrics.read_metrics(os.getpid())
        self.assertFalse(data['io_available']);self.assertNotIn('exited_or_unreadable',data)
        self.assertIn('cpu_ticks',data)

    def test_bounded_named_markers_do_not_copy_private_text(self):
        with tempfile.TemporaryDirectory() as temp:
            game=Path(temp);(game/'logs').mkdir()
            (game/'logs/crossmix-client.log').write_text('access_token=PRIVATE_SENTINEL\nLoaded Minecraft library\n'
                'Successfully registerered XboxLiveAppConfig methods\n')
            child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(1)'])
            try:
                monitor=subprocess.Popen([sys.executable,str(C/'session_metrics.py'),str(game),str(child.pid),str(os.getpid())],
                    stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                child.wait(timeout=3);monitor.communicate(timeout=4)
                self.assertEqual(monitor.returncode,0)
                text=(game/'logs/crossmix-performance.jsonl').read_text()
                self.assertNotIn('PRIVATE_SENTINEL',text)
                data=[json.loads(s) for s in text.splitlines()]
                self.assertTrue(any(s['event']=='minecraft_library_loaded' for s in data))
                self.assertTrue(any(s['event']=='xbox_sdk_registered' for s in data))
            finally:
                if child.poll() is None:child.kill();child.wait()
                if monitor.poll() is None:monitor.kill();monitor.wait()


if __name__=='__main__':unittest.main()
