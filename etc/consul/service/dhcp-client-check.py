#!/usr/bin/python3.6
import json
from subprocess import getoutput
import sys


def main():
    output = getoutput('sudo dhtest -i eth0 -T 5 -g 10.111.222.254 -j')
    if len(json.loads(output)) == 4:
        sys.exit(0)
    else:
        sys.exit(1)    


if __name__ == "__main__":
        main()


