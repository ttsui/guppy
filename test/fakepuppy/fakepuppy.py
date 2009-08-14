#!/usr/bin/python

## fakepuppy.py - Puppy simulator program
## Copyright (C) 2005-2009 Tony Tsui <tsui.tony@gmail.com>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import sys
import getopt
import time
import os
import signal
import fcntl

FAIL_START    = False
FAIL_TRANSFER = False
FAIL_TRANSFER_NO_SRC = False
FAIL_LIST     = False
FAIL_LIST_MIDWAY = True
FAIL_SIZE     = False
FAIL_NO_PVR   = False

DOWNLOAD_RATE = 50

SLOW_LISTDIR = False

DATA_DIR='/local/devel/guppy/test/fakepuppy/'

def check_fail(fail, fail_msg):
	if fail:
		print fail_msg
		sys.exit(1)


check_fail(FAIL_START, 'FAIL_START')

lock_filename =  '/tmp/' + os.path.basename(sys.argv[0])

lock_file = open(lock_filename, 'a')

try:
	fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
except:
	print 'ERROR: Can not obtain exclusive lock on ' + lock_filename
	sys.exit(8)

opts, args = getopt.getopt(sys.argv[1:], 'c:ti')

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

check_fail(FAIL_NO_PVR, 'ERROR: Can not autodetect a Topfield TF5000PVRt')

if transfer:
	check_fail(FAIL_TRANSFER, 'FAIL_TRANSFER')

	check_fail(FAIL_TRANSFER_NO_SRC, 'ERROR: Device reports Invalid command')

	if len(args) != 2:
		print 'ERROR: Insufficent arguments for transfer command'
		sys.exit(1)
	
	src = args[0]
	dst = args[1]

	try:
		file = open(dst, 'w')
	except IOError, error:
		print error
		sys.exit(13)

	inc = DOWNLOAD_RATE
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
	check_fail(FAIL_LIST, 'FAIL_LIST')

	dir = ''
	if len(args) > 0 and len(args[0]):
		if args[0][0] != '\\':
			dir = '-'
		if args[0] != '\\':
			dir += args[0].replace('\\', '-')
	if dir.find('MOVIES') != -1:
		check_fail(FAIL_LIST_MIDWAY, 'ERROR: Device reports Invalid command')
	list_file = 'puppy-dir' + dir + '.txt'
	listing = open(DATA_DIR + list_file)
	for line in listing:
		print line,
	listing.close()
	if SLOW_LISTDIR:
		time.sleep(0.5)
elif size:
	check_fail(FAIL_SIZE, '''FAIL_SIZE''')
	print 'Total %10u kiB %7u MiB %4u GiB' % (0, 0, 120)
	print 'Free  %10u kiB %7u MiB %4u GiB' % (0, 500, 0)
elif cancel:
	sys.exit(1)
else:
	print opts, '|', args,

lock_file.close()
