#!/usr/bin/python2
import subprocess
import sys
import os
os.chdir('/etc/consul/service/')
p = subprocess.Popen('/sbin/fping -m -u -r 0  -f ciscoip', shell=True,  stdout=subprocess.PIPE)
out = p.stdout.read().split() #fping hosts from ciscoip file and split to list
with open('ciscoip') as f:
	a = len(f.readlines())
if len(out) > a/2:
	sys.exit(1)
else:
	sys.exit(0)	

