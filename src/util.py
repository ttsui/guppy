## util.py - Utility functions
## Copyright (C) 2005 Tony Tsui <tsui.tony@gmail.com>
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