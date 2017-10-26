#!/bin/python
import psycopg2
import sys
def main():
	try:
		conn_string = "host='localhost' port='25432' user='postgres' password='611621Skynet'"
		conn = psycopg2.connect(conn_string)
		cursor = conn.cursor()
	except:
		sys.exit(1)
	else: sys.exit(0)


if __name__ == "__main__":
	main()
 
