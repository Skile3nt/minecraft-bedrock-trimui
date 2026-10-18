#!/usr/bin/env python3
"""Focused tests for sparse per-thread CPU attribution."""
import tempfile
from pathlib import Path
import unittest

from session_metrics import read_thread_cpu


def stat_line(tid, name, ticks):
    fields=['R']+[0]*12
    fields[11]=ticks  # field 14 (utime) after state/comm
    fields[12]=0      # field 15 (stime)
    return f'{tid} ({name}) '+' '.join(map(str,fields))+'\n'


class ThreadMetricsTests(unittest.TestCase):
    def test_top_five_deltas_and_new_threads(self):
        with tempfile.TemporaryDirectory() as temp:
            task=Path(temp)/'123/task'
            for tid in range(1,8):
                p=task/str(tid);p.mkdir(parents=True)
                (p/'comm').write_text(f'worker{tid}\n')
                (p/'stat').write_text(stat_line(tid,f'worker{tid}',10))
            previous,_=read_thread_cpu(123,proc_root=Path(temp),hz=100)
            for tid in range(1,8):
                p=task/str(tid)
                (p/'stat').write_text(stat_line(tid,f'worker{tid}',10+tid*10))
            (task/'8').mkdir();(task/'8/comm').write_text('new-thread\n')
            (task/'8/stat').write_text(stat_line(8,'new-thread',1000))
            current,top=read_thread_cpu(123,previous,10,Path(temp),100)
            self.assertEqual(len(current),8)
            self.assertEqual([row['tid'] for row in top],[7,6,5,4,3])
            self.assertTrue(all(row['cpu_percent_one_core']==row['tid'] for row in top))

    def test_missing_process_is_nonfatal(self):
        self.assertEqual(read_thread_cpu(404,proc_root=Path('/nonexistent')),({},[]))


if __name__=='__main__': unittest.main()
