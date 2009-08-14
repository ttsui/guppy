## util.py - Utility functions
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

import math
import os

GUPPY_CONF_FILE = os.environ['HOME'] + '/' + '.guppy'
	
def humanReadableSize(size):
	div_count = 0
	new_size = size
	prev_size = new_size
	
	while new_size > 0 and new_size > 1000:
		div_count += 1
		prev_size = new_size
		new_size = new_size/1024
	
	if prev_size > 1000:
		# Divide by float for more precise number
		human_size = "%.1f" % (prev_size / 1024.0)
	else:
		human_size = str(prev_size)
	
	if div_count == 1:
		human_size += ' KB'
	elif div_count == 2:
		human_size += ' MB'
	elif div_count == 3:
		human_size += ' GB'
	else:
		human_size += ' B'

	return human_size

def convertToBytes(size):
	size, unit = size.split()

	size = float(size)
	
	if unit == 'GB':
		size = size * math.pow(1024, 3)
	elif unit == 'MB':
		size = size * math.pow(1024, 2)
	elif unit == 'KB':
		size = size * 1024
		
	return size

def getConfValue(key):
	""" Get the config value for key.
	
		Return: Config value if successfully retrieved
		        None otherwise
	"""
	try:
		file = open(GUPPY_CONF_FILE, 'r')
	except IOError, error:
		print 'ERROR: Opening ', GUPPY_CONF_FILE, ':', error
		return None
	
	for line in file:
		if line.startswith('#') or line.find('=') == -1:
			continue
		akey, value = line.split('=', 1)
		if akey == key:
			return value.rstrip('\n')
		
	return None

def setConfValue(key, value):
	""" Set the config value for key.
	
		Return: True if config value successfully set.
		        False otherwise
	"""
	try:
		file = open(GUPPY_CONF_FILE, 'r+')
	except IOError, error:
		if str(error).find('[Errno 2]') != -1:
			try:
				file = open(GUPPY_CONF_FILE, 'w+')
			except IOError, error:
				print 'ERROR: Writing to', GUPPY_CONF_FILE, ':', error
				return False
		else:
			return False
	
	cur_conf = file.readlines()
	new_conf = []
	key_updated = False
	
	for line in cur_conf:
		if line.startswith('#') or line.find('=') == -1:
			new_conf.append(line)
			continue
		
		akey, avalue = line.split('=', 1)
		if akey == key:
			new_conf.append(key + '=' + value + '\n')
			key_updated = True
		else:
			new_conf.append(line)

	# Handle if conf key did not exist in the conf file		
	if key_updated is False:
		new_conf.append(key + '=' + value + '\n')

	# Clear file
	file.truncate(0)
	file.seek(0)

	# Write new config values
	file.writelines(new_conf)

	file.close()
	
	return True
		