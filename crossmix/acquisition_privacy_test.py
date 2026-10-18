#!/usr/bin/env python3
"""Exercise output suppression and credential cleanup with synthetic sessions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).with_name("acquire_owned_apks.py")
RECOVERY = SOURCE.parent.parent / "recovery/play-acquisition"
MARKER = "SYNTHETIC_SECRET_MUST_NOT_BE_LOGGED"


class PrivacyTests(unittest.TestCase):
    def exercise(self, fail_download):
        with tempfile.TemporaryDirectory(dir=RECOVERY, prefix="privacy-test-") as temporary:
            root = Path(temporary)
            (root / "crossmix").mkdir()
            controller = root / "crossmix/acquire_owned_apks.py"
            controller.write_bytes(SOURCE.read_bytes())
            helper = root / "tools/mcbedrock-get"
            helper.mkdir(parents=True)
            (helper / "signin.py").write_text('''import os
from pathlib import Path
def forget():
    (Path(os.environ['MCBEDROCK_DATA_DIR'])/'account.json').unlink(missing_ok=True)
''')
            (helper / "mcbedrock_get.py").write_text(f'''import os,sys
from pathlib import Path
from types import SimpleNamespace
def interactive_login(address=''):
    print({MARKER!r}); print({MARKER!r},file=sys.stderr)
    (Path(os.environ['MCBEDROCK_DATA_DIR'])/'account.json').write_text({MARKER!r})
    return SimpleNamespace(email='synthetic@example.invalid',master_token={MARKER!r})
''')
            (helper / "requests.py").write_text('''from types import SimpleNamespace
class Session:
    def request(self,*args,**kwargs): return None
sessions=SimpleNamespace(Session=Session)
''')
            (helper / "linux_backend.py").write_text(f'''import os
from pathlib import Path
def ensure_device_profile(abi): assert abi=='arm64'
def sign_in(email,token):
    for n in ['playdl.conf','token_cache.conf','device-arm64.conf.state']:
        (Path(os.environ['MCBEDROCK_DATA_DIR'])/n).write_text(token)
def download(code,output,on_line,timeout,abi):
    assert code==971622101 and abi=='arm64'
    on_line({MARKER!r}); on_line('Downloaded 50%')
    if {fail_download!r}: raise RuntimeError({MARKER!r})
    p=output/'synthetic.apk';p.write_bytes(b'fixture');return [p]
def sign_out():
    for n in ['playdl.conf','token_cache.conf']:
        (Path(os.environ['MCBEDROCK_DATA_DIR'])/n).unlink(missing_ok=True)
    return True
''')
            (root / "Downloads").mkdir()
            bootstrap = f"from pathlib import Path; import runpy; Path.home=classmethod(lambda cls:Path({str(root)!r})); module=runpy.run_path({str(controller)!r},run_name='privacy_fixture'); module['main'].__globals__['ask_address_gtk']=lambda **kwargs:'synthetic@example.invalid'; raise SystemExit(module['main']())"
            process = subprocess.run([sys.executable, "-c", bootstrap], capture_output=True, timeout=15)
            work = root / "recovery/play-acquisition"
            report = (work / "acquisition-status.json").read_text()
            self.assertNotIn(MARKER, report)
            self.assertEqual(process.stdout, b"")
            self.assertEqual(process.stderr, b"")
            outcome = json.loads(report)
            self.assertTrue(outcome["credentials_removed"])
            for name in ['account.json','playdl.conf','token_cache.conf','device-arm64.conf.state']:
                self.assertFalse((work / "private-session" / name).exists())
            self.assertEqual(process.returncode, 1 if fail_download else 0)
            return outcome

    def test_success_discards_raw_output_and_removes_session(self):
        result = self.exercise(False)
        self.assertEqual(result['result'], 'downloaded_pending_signature_validation')

    def test_failure_does_not_log_exception_secret_and_removes_session(self):
        result = self.exercise(True)
        self.assertEqual(result['result'], 'stopped')
        self.assertEqual(result['failed_stage'], 'download')


if __name__ == '__main__':
    unittest.main()
