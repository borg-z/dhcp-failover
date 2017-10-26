#!/usr/bin/python3
from subprocess import getoutput
import sys

def main():
    dhcp4status = getoutput('keactrl status').split()[2]
    if dhcp4status == 'active':
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
	main()

