## puppy.py - Puppy class to wrap calls to puppy
## Copyright (C) 2005-2006 Tony Tsui <tsui.tony@gmail.com>
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
import inspect
import os
import popen2
import signal
import time
import fcntl
import re

# Set to True for debug output
DEBUG = False

class Puppy:
	LOCK_FILE = '/tmp/puppy'
	
	# puppy error code for lock failure
	E_GLOBAL_LOCK = 8
	E_HDD_NOT_READY = 185
	
	def __init__(self):
		self.cmd = 'guppy-puppy'
		self.turbo = False
		self.popen_obj = None

		# FIXME: Toppy may not always be latin_1, i.e. ISO-8859-1. How do we
		#        find out what encoding to use?		
		self.encoding = 'latin_1'
		
	def cancelTransfer(self):
		if self.getStatus(wait=False) == None:
			return
			
		if self.getStatus(wait=False) == -1:
			os.kill(self.popen_obj.pid, signal.SIGTERM)
			
		# Reap child process
		self.popen_obj.wait()
		
		return

	def delete(self, filename):
		args = ['-c', 'delete', filename]
		
		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()
		
		if self.getStatus() != 0:
			self._handleErrorOuput(output)
		
		return

	def getDiskSpace(self):
		args = ['-c', 'size']

		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()

		if self.getStatus() != 0:
			self._handleErrorOuput(output)

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

	# FIXME: Can getFile() be merged with putFile()
	def getFile(self, src_file, dest_file=None):
		args = ['-i', '-c', 'get', src_file]
		if dest_file != None:
			args.append(dest_file)
		else:
			args.append(os.path.basename(src_file))
			
		self.progress_output = self._execute(args)

		status = self.getStatus(wait=False)
		if status != 0 and status != -1:
			output = self.progress_output.readlines()
			self._handleErrorOuput(output)
			
		return

	def getProgress(self):
		exit_status = self.getStatus(wait=False)
		
		# exit_status of -1 means process is still alive
		if exit_status != -1:
			# Raise exception if puppy did not exit successfully or because of
			# SIGTERM.
			if exit_status != 0 and exit_status != 15:
				raise PuppyError("puppy did not exit successfully or a SIGTERM was received.")

			# Reap child process
			if exit_status == 0:
				self.getStatus()
			
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
			# Reap child process
			exit_status = self.getStatus()
			if exit_status != 0 and exit_status != 15:
				self._handleErrorOuput([line])
			
			return None, None, None

		percent = tokens[0][:tokens[0].rindex('%')]
		
		speed = tokens[1]
		
		elapsed = tokens[2].split()
		remaining = tokens[3].split()
		time = { 'elapsed' : elapsed[0], 'remaining' : remaining[0] }
		
		return percent, speed, time

	def getStatus(self, wait=True):
		if self.popen_obj == None:
			return None
			
		if wait:
			status = os.WEXITSTATUS(self.popen_obj.wait())
		else:
			status = self.popen_obj.poll()
			
		return status

	def isActive(self):
		lock_file = open(Puppy.LOCK_FILE, 'a')
		
		try:
			fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
			result = False
		except:
			result = True
			
		lock_file.close()
	
		return result
		
	def listDir(self, path=None):
		args = ['-c', 'dir']
		if path != None:
			args.append(path)
			
		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()

		status = self.getStatus()	
		if status == Puppy.E_GLOBAL_LOCK:
			raise PuppyBusyError(str(output))
		elif status != 0:
			self._handleErrorOuput(output)
		
		regex = re.compile(r"([df])\s+(\d+)\s+(\w+\s+\w+\s+\d+\s+[\d:]+\s+\d+)\s+(.+)")
		listing = []
		
		for line in output:
			entry = regex.match(line)

			# Convert from Toppy's code page of ISO-8859-1 to UTF-8
			# FIXME: Toppy may not always be ISO-8859-1. How do we find out
			#        what encoding to use?
			filename = unicode(entry.group(4), self.encoding, 'replace')
			filename = filename.encode('utf-8')

			date = unicode(entry.group(3), self.encoding, 'replace')
			date = date.encode('utf-8')

			item = [ entry.group(1), filename, date, entry.group(2) ]
			listing.append(item)
		
		return listing
		
	def makeDir(self, dirname):
		args = ['-c', 'mkdir', dirname]
			
		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()
		
		if self.getStatus() != 0:
			self._handleErrorOuput(output)
		
		return

	def putFile(self, src_file, dest_file=None):
		args = ['-c', 'put', src_file]
		if dest_file != None:
			args.append(dest_file)
		else:
			args.append(os.path.basename(src_file))
			
		self.progress_output = self._execute(args)
		
		status = self.getStatus(wait=False)
		if status != 0 and status != -1:
			output = self.progress_output.readlines()
			self._handleErrorOuput(output)
			
		return

	def rename(self, old_name, new_name):
		args = ['-c', 'rename', old_name, new_name]

		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()

		if self.getStatus() != 0:
			self._handleErrorOuput(output)
		
		return

	def reset(self):	
		args = ['-c', 'cancel']
		
		try:	
			output_file = self._execute(args)
		except PuppyBusyError:
			return False

		output_file.readlines()
		output_file.close()
		
		if self.getStatus() != 0:
			return False
		
		return True

	def setTurbo(self, value):
		args = ['-c', 'turbo']
			
		if value == True:
			args += '1'
		else:
			args += '0'
			
		output_file = self._execute(args)

		output = output_file.readlines()
		output_file.close()
		
		if self.getStatus() != 0:
			self._handleErrorOuput(output)
		
		return
			
	def _execute(self, args_list):
		cmd = [ self.cmd ] + args_list
		
		if DEBUG:
			print 'cmd = ', cmd

		for i in xrange(len(cmd)):
			arg = unicode(cmd[i])
			cmd[i] = arg.encode(self.encoding)
		
		if self.isActive():
			raise PuppyBusyError('Can not get exclusive lock on ' + Puppy.LOCK_FILE)
			
		self.popen_obj = popen2.Popen4(cmd)
		self.popen_obj.tochild.close()
		
		status = self.getStatus(wait=False)
		if status == Puppy.E_GLOBAL_LOCK:
			raise PuppyBusyError(self.popen_obj.fromchild.readlines())
		elif status == Puppy.E_HDD_NOT_READY:
			time.sleep(1)
			self.popen_obj = popen2.Popen4(cmd)
			self.popen_obj.tochild.close()
			
		return self.popen_obj.fromchild

	def _handleErrorOuput(self, output_lines):
		"""Parse puppy error message and raise appropriate exception.
		
		"""
		caller = sys._getframe(1)
		try:
			func_name = inspect.getframeinfo(caller)[2]
		finally:
			del caller

		errmsg = ' '.join(output_lines)
		msg = func_name + '(): ' + errmsg
		
		# Print puppy error message to stderr
		print >> sys.stderr, msg
		
		if errmsg.startswith('ERROR: Can not autodetect a Topfield TF5000PVRt'):
			raise PuppyNoPVRError(msg)
		elif errmsg.startswith('ERROR: Device reports Invalid command') or \
		     errmsg.startswith('ERROR: Can not open source file: No such file or directory'):
			raise PuppyError(_('The file you are trying to transfer is no longer available.'))
		else:
			raise PuppyError(msg)
		
class PuppyError(Exception):
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return self.value

class PuppyBusyError(PuppyError):
	"""Exception raised for when another instance of Puppy is running.
	
	"""
	def __init__(self, value):	
		PuppyError.__init__(self, value)

class PuppyNoPVRError(PuppyError):
	"""Excpetion raised when no PVR is detected.
	
	"""
	def __init__(self, value):
		msg = _('PVR not connected. Please check that your computer is connected to the PVR.')
		PuppyError.__init__(self, msg)
	
