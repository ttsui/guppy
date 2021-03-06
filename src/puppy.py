## puppy.py - Puppy class to wrap calls to puppy
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
## Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import os
import popen2
import signal

# Set to True for debug output
DEBUG = False

class Puppy:
	def __init__(self):
		self.cmd = 'puppy'
		self.turbo = False
		
	def cancelTransfer(self):
		if self.getStatus(wait=False) == -1:
			os.kill(self.popen_obj.pid, signal.SIGTERM)
		
		return

	def getDiskSpace(self):		
		args = '-c size'

		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()

		if self.getStatus() != 0:
			raise PuppyError("getDiskSpace() failed. puppy returned: " + str(output))

		# Skip Total size line
		total = float(output[0].split()[5]) * 1024 * 1024 * 1024
		
		free = output[1].split()
		
		# GB free is 5th entry
		idx = 5
		free_space = float(free[idx])
		# Search for first non-zero unit
		while free_space < 1 and idx != 0:
			idx -= 2
			free_space = float(free[idx])

		# Convert to bytes
		idx = (idx / 2) + 1
		for i in xrange(idx):
			free_space *= 1024

		return total, free_space

		
	def listDir(self, path=None):
		args = '-c dir'
		if path != None:
			args += ' ' + path
			
		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()
		
		listing = []
		# Parse output of output_file and return it as a list
		for line in output:
			entry = line.split()
			space = ' '
			item = [ entry[0], space.join(entry[7:]),
			         "%s %s %s %s" % (entry[2], entry[3], entry[4], entry[6]),
			         entry[1] ]
			listing.append(item)
			
		if self.getStatus() != 0:
			raise PuppyError("listDir failed. puppy returned: " + str(output))
		
		return listing
		
		# FIXME: Can getFile() be merged with putFile()
	def getFile(self, src_file, dest_file=None):
		args = '-c get' + ' "' + src_file + '"'
		if dest_file != None:
			args += ' "' + dest_file + '"'
		else:
			args += ' "' + os.path.basename(src_file) + '"'
			
		self.progress_output = self._execute(args)
		
		return

	def putFile(self, src_file, dest_file=None):
		args = '-c put' + ' "' + src_file + '"'
		if dest_file != None:
			args += ' "' + dest_file + '"'
		else:
			args += ' "' + os.path.basename(src_file) + '"'
			
		self.progress_output = self._execute(args)
		
		return

	def makeDir(self, dirname):
		args = '-c mkdir' + ' ' + dirname
			
		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()
		
		# Parse output of output_file and return it as a list
		
		if self.getStatus() != 0:
			raise PuppyError("makeDir failed. puppy returned: " + str(output))
		
		return

	def rename(self, old_name, new_name):
		args = '-c rename' + ' ' + old_name + ' ' + new_name
			
		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()
		
		# Parse output of output_file and return it as a list
		
		if self.getStatus() != 0:
			raise PuppyError("rename failed. puppy returned: " + str(output))
		
		return

	def delete(self, filename):
		args = '-c delete' + ' ' + filename
			
		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()
		
		# Parse output of output_file and return it as a list
		
		if self.getStatus() != 0:
			raise PuppyError("delete failed. puppy returned: " + str(output))
		
		return

	def getProgress(self):
		exit_status = self.getStatus(wait=False)
		if exit_status != -1:
			if exit_status != 0 and exit_status != 15:
				raise PuppyError("Transfer failed")
			
		# Move to first non \r character
		char = self.progress_output.read(1)
		while char == '\r':
			char = self.progress_output.read(1)

		line = char
		# Read all characters up to \r
		while char != '\r' and char != '':
			char = self.progress_output.read(1)
			line += char

		tokens = line.split(',')
		
		if len(tokens) != 4:
			return None, None, None

		percent = tokens[0][:tokens[0].rindex('%')]
		
		speed = tokens[1]
		
		elapsed = tokens[2].split()
		remaining = tokens[3].split()
		time = { 'elapsed' : elapsed[0], 'remaining' : remaining[0] }
		
		return percent, speed, time

	def getStatus(self, wait=True):
		if wait:
			status = os.WEXITSTATUS(self.popen_obj.wait())
		else:
			status = self.popen_obj.poll()
			
		return status
		
	def setTurbo(self, value):
		self.turbo = value
		
	def _execute(self, args):
		cmd = self.cmd
		if self.turbo == True:
			cmd += ' -t'
		cmd += ' ' + args
		
		if DEBUG:
			print 'cmd = ', cmd
		
		self.popen_obj = popen2.Popen4(cmd)
		self.popen_obj.tochild.close()
		
		return self.popen_obj.fromchild

class PuppyError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return repr(self.value)
