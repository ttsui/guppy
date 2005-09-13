#!/usr/bin/python

import sys
import getopt
import time
import os
import signal
import fcntl

SLOW_LISTDIR = False

DATA_DIR='/local/devel/guppy/testing/'

lock_filename =  '/tmp/' + os.path.basename(sys.argv[0])

lock_file = open(lock_filename, 'a')

try:
	fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except:
	print 'ERROR: Can not obtain exclusive lock on ' + lock_filename
	sys.exit(8)

opts, args = getopt.getopt(sys.argv[1:], 'c:t')

transfer = False
listdir = False
size = False
cancel = False

for opt, optarg in opts:
	if opt == '-c':
		if optarg == 'get' or optarg == 'put':
			transfer = True
		if optarg == 'dir':
			listdir = True
		if optarg == 'cancel':
			cancel = True
		if optarg == 'size':
			size = True

if transfer:
	print 'args = ', args
	if len(args) != 2:
		print 'ERROR: Insufficent arguments for transfer command'
		sys.exit(1)
	
	src = args[0]
	dst = args[1]

	file = open(dst, 'w')

	inc = 5
	percent = 0.0
	for i in xrange(100/inc):
		percent = percent + inc
		print >> sys.stderr, "\r%6.2f%%, %5.2f Mbits/s, %02d:%02d:%02d elapsed, %d:%02d:%02d remaining" % (percent, 2.2, 1, 1, 1, 2, 2, 2),
		file.write(str(percent) + '\n')
		time.sleep(0.5)
#		if percent > 15:
#			sys.exit(1)

	file.close()
	print
elif listdir:
	dir = ''
	if len(args) > 0 and len(args[0]):
		if args[0][0] != '\\':
			dir = '-'
		dir += args[0].replace('\\', '-')
	list_file = 'puppy-dir' + dir + '.txt'
	listing = open(DATA_DIR + list_file)
	for line in listing:
		print line,
	listing.close()
	if SLOW_LISTDIR:
		time.sleep(0.5)
elif size:
	print 'Total %10u kiB %7u MiB %4u GiB' % (0, 0, 120)
	print 'Free  %10u kiB %7u MiB %4u GiB' % (0, 500, 0)
elif cancel:
	sys.exit(1)
else:
	print opts, '|', args,

lock_file.close()
