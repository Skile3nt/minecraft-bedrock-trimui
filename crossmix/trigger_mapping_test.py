#!/usr/bin/env python3
"""Exercise the pinned upstream parser/Gamepad, not a reimplemented mapping.

Pass the linux-gamepad source directory as argv[1]. Audited revision:
68d75a74f80a93ec4ff7a96eea0909df28d45330. Synthetic input is not physical proof.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

C=Path(__file__).resolve().parent
source=Path(sys.argv[1])
mapping=next(x for x in (C/'trimui.gamecontrollerdb.txt').read_text().splitlines() if not x.startswith('#'))
fields=dict(x.split(':',1) for x in mapping.split(',')[2:] if ':' in x)
assert fields['lefttrigger']=='a2' and fields['righttrigger']=='a5'
assert fields['leftshoulder']=='b4' and fields['rightshoulder']=='b5'
assert fields['rightx']=='a3' and fields['righty']=='a4'
assert len(fields)==21
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);(p/'check.cpp').write_text(r'''
#include <gamepad/gamepad.h>
#include <gamepad/gamepad_mapping.h>
#include <gamepad/joystick.h>
#include <cassert>
#include <cmath>
#include <fstream>
#include <string>
using namespace gamepad;
struct Pad:Joystick{
 float axes[6]={0,0,-1,0,0,-1};
 std::string getGUID()const override{return "030000005e0400008e02000014010000";}
 bool getButton(int)const override{return false;}
 float getAxis(int i)const override{return axes[i];}
 int getHat(int)const override{return 0;}
};
int main(int,char**argv){
 std::ifstream f(argv[1]);std::string line;
 while(std::getline(f,line))if(!line.empty() && line[0]!='#')break;
 GamepadMapping m;m.parse(line);Pad p;Gamepad g(0,p,m);
 assert(g.getAxis(GamepadAxis::LEFT_TRIGGER)==0 && g.getAxis(GamepadAxis::RIGHT_TRIGGER)==0);
 p.axes[2]=1;assert(g.getAxis(GamepadAxis::LEFT_TRIGGER)==1 && g.getAxis(GamepadAxis::RIGHT_TRIGGER)==0);
 p.axes[5]=1;assert(g.getAxis(GamepadAxis::RIGHT_TRIGGER)==1 && g.getAxis(GamepadAxis::LEFT_TRIGGER)==1);
 p.axes[2]=-1;assert(g.getAxis(GamepadAxis::LEFT_TRIGGER)==0 && g.getAxis(GamepadAxis::RIGHT_TRIGGER)==1);
 p.axes[5]=-1;assert(g.getAxis(GamepadAxis::RIGHT_TRIGGER)==0);
 p.axes[3]=.7f;assert(std::abs(g.getAxis(GamepadAxis::RIGHT_X)-.7f)<.00001f);
}
''')
    subprocess.run(['g++','-std=c++17','-I'+str(source/'include'),str(p/'check.cpp'),
                    str(source/'gamepad.cpp'),str(source/'gamepad_mapping.cpp'),'-o',str(p/'check')],check=True)
    subprocess.run([str(p/'check'),str(C/'trimui.gamecontrollerdb.txt')],check=True)
print('PASS pinned upstream trigger parser: independent press/release/both held and right stick; synthetic PC input')
