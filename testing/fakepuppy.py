#!/usr/bin/python

import sys
import getopt
import time
import os

DATA_DIR='/local/devel/guppy/testing/'

opts, args = getopt.getopt(sys.argv[1:], 'c:t')

transfer = False
listdir = False

for opt, optarg in opts:
	if opt == '-c':
		if optarg == 'get' or optarg == 'put':
			transfer = True
		if optarg == 'dir':
			listdir = True
		if optarg == 'cancel':
			os.system("pkill -f 'fakepuppy.py -c get.*'")
		if optarg == 'size':
			size = True

if transfer:
	inc = 10
	percent = 0.0
	for i in xrange(100/inc):
		percent = percent + inc
		print >> sys.stderr, "\r%6.2f%%, %5.2f Mbits/s, %02d:%02d:%02d elapsed, %d:%02d:%02d remaining" % (percent, 2.2, 1, 1, 1, 2, 2, 2),
		time.sleep(0.5)
	print
elif listdir:
	listing = open(DATA_DIR + 'puppy-listdir.txt')
	for line in listing:
		print line,
	listing.close()
elif size:
	print 'Total %10u kiB %7u MiB %4u GiB' % (0, 0, 120)
	print 'Free  %10u kiB %7u MiB %4u GiB' % (0, 500, 0)
else:
	print opts, '|', args,
