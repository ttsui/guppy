## FileSystemModel.py - FileSystemModel class
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

import os
import stat
import time
import string
import copy
import threading

import gtk
import gobject

import puppy
from util import *

# Set to True for debug output
DEBUG = False

class FileSystemModel(gtk.ListStore):
	TYPE_COL, ICON_COL, NAME_COL, DATE_COL, SIZE_COL = range(5)

	def __init__(self):
		self.current_dir = None
		gtk.ListStore.__init__(self, gobject.TYPE_STRING, gobject.TYPE_STRING,
		                             gobject.TYPE_STRING, gobject.TYPE_STRING,
		                             gobject.TYPE_STRING)

	def find(self, name):
		for row in self:
			if name == row[FileSystemModel.NAME_COL]:
				return row
				
		return None
			
	def getCWD(self):
		return self.current_dir
	
	def sort_func(self, model, iter1, iter2, col=None):
		type1 = model.get_value(iter1, FileSystemModel.TYPE_COL)
		type2 = model.get_value(iter2, FileSystemModel.TYPE_COL)
		
		if type1 == type2:
			if col == FileSystemModel.NAME_COL:
				return self.string_sort_func(model, iter1, iter2, col)
			elif col == FileSystemModel.DATE_COL:
				return self.date_sort_func(model, iter1, iter2, col)
			elif col == FileSystemModel.SIZE_COL:
				return self.size_sort_func(model, iter1, iter2, col)
			else:
				# FIXME: Raise exception here
				print "ERROR: Unknown column type: ", col
				return 0
		elif type1 == 'f' and type2 == 'd':
			return 1
		else:
			return -1
	
	def string_sort_func(self, model, iter1, iter2, col=None):
		string1 = string.lower(model.get_value(iter1, col))
		string2 = string.lower(model.get_value(iter2, col))

		if string1 == string2:
			return 0;
		elif string1 < string2:
			return -1
		else:
			return 1

	def date_sort_func(self, model, iter1, iter2, col=None):
		# Date column is empty for '..' directory
		date1_str = model.get_value(iter1, col)
		if len(date1_str) == 0:
			return -1
		
		date2_str = model.get_value(iter2, col)
		if len(date2_str) == 0:
			return 1

		format = '%a %b %d %Y'
		date1 = time.strptime(date1_str, format)
		date2 = time.strptime(date2_str, format)

		if date1 == date2:
			return self.string_sort_func(model, iter1, iter2, FileSystemModel.NAME_COL);
		elif date1 < date2:
			return -1
		else:
			return 1

	def size_sort_func(self, model, iter1, iter2, col=None):
		size1 = model.get_value(iter1, col).split()
		size2 = model.get_value(iter2, col).split()

		size1_len = len(size1)
		size2_len = len(size2)
		
		if size1_len < size2_len:
			return -1
		elif size1_len > size2_len:
			return 1
		else:
			return 0

		unit_weight = { 'B' : 1, 'KB' : 2, 'MB' : 3, 'GB' : 4 }

		# Sizes in bytes may not have 'B' unit postfix
		if len(size1) < 2:
			size1[1] = unit_weight['B']
		else:
			size1[1] = unit_weight[size1[1]]

		return 1
		# Sizes in bytes may not have 'B' unit appended
		if len(size2) < 2:
			size2[1] = unit_weight['B']
		else:
			size2[1] = unit_weight[size2[1]]
			
		if size1[1] == size2[1]:
			size1[0] = float(size1[0])
			size2[0] = float(size2[0])
			if size1[0] == size2[0]:
				return self.string_sort_func(model, iter1, iter2, FileSystemModel.NAME_COL);
			elif size1[0] < size2[0]:
				return -1
			else:
				return 1
		elif size1[1] < size2[1]:
			return -1
		else:
			return 1

class PCFileSystemModel(FileSystemModel):
	def __init__(self):
		FileSystemModel.__init__(self)
		
		# FIXME: Get dir from when Guppy last exited
		self.current_dir = os.environ['HOME']
		
		self.changeDir()
		
	def changeDir(self, dir=None):
		if dir:
			if dir[0] != '/':
				dir = self.current_dir + '/' + dir
		else:
			dir = self.current_dir

		dir = os.path.normpath(dir)
		
		if not os.access(dir, os.F_OK):
			return

		self.current_dir = dir
			
		if len(self) > 0:
			self.clear()
		
		# Parent directory
		self.append(['d', gtk.STOCK_DIRECTORY, '..', '', ''])
		
		for file in os.listdir(self.current_dir):
			try:
				mode = os.stat(self.current_dir + '/' + file)
			except OSError, (errno, strerror):
				print 'PCFileSystemModel::changeDir(): OSError(%s): %s\n' % (errno, strerror)
				continue

			if stat.S_ISDIR(mode[stat.ST_MODE]):
				type = 'd'
				icon = gtk.STOCK_DIRECTORY
				size = ''
			else:
				type = 'f'
				icon = gtk.STOCK_FILE
				size = humanReadableSize(mode[stat.ST_SIZE])
			
			mtime = time.strftime('%a %b %d %Y', time.localtime(mode[stat.ST_MTIME]))
			entry = [ type, icon, file, mtime, size ]
			self.append(entry)

	def freeSpace(self):
		cmd = 'df ' + '"' + self.current_dir + '"'
		pipe = os.popen(cmd)

		# Skip Headers
		pipe.readline()
		output = pipe.readline().split()

		exit_stat = pipe.close()
		if exit_stat != None and os.WEXITSTATUS(exit_stat) != 0:
			# TODO: Raise exception
			print "ERROR: Failed to get disk free space (`%s')" % (cmd)
			return None
		
		# Multiple by 1024 to convert from kilobytes to bytes
		return humanReadableSize(int(output[3])*1024)


class PVRFileSystemModel(FileSystemModel):
	def __init__(self):
		FileSystemModel.__init__(self)

		# FIXME: Get dir from when Guppy last exited
		# We need to use an empty string to list the PVR root directory.
		self.current_dir = '\\'

		self.freespace = 0
				
		self.puppy = puppy.Puppy()

		self.dir_tree_lock = threading.Lock()

		self.dir_tree = None
		self.updateCache()
		
		# The cache may not have been updated because puppy was busy. Try again.
		if self.dir_tree == None:
			self.updateCache()
					
		self.changeDir()

	def changeDir(self, dir=None):
		"""Change directory and update model data accordingly.
		"""
		print 'changeDir(): dir = ', dir
		if dir:
			# Append CWD if dir is not an absolute path
			if dir[0] != '\\':
				if self.current_dir[-1] != '\\':
					dir = self.current_dir + '\\' + dir
				else:
					dir = self.current_dir + dir
		else:
			dir = self.current_dir

		norm_path = os.path.normpath(dir.replace('\\', '/'))
		# norm_path is '.' when _dir_ is an empty string. _dir_ is an empty
		# string for the PVR root directory.
		# Also don't change dir when changing to '..' directory.
		if norm_path == '.' or norm_path == '..':
			dir = '\\'
		else:
			dir = norm_path.replace('/', '\\')

		print 'changeDir(): dir2 = ', dir		
		dir_node = self.findDirectory(dir)
		
		self.current_dir = dir
		
		# Clear model
		if len(self) > 0:
			self.clear()

		for file_name, file_info in dir_node.getFiles():  
			file_info.insert(FileSystemModel.ICON_COL, gtk.STOCK_FILE)
		
			file_info[FileSystemModel.SIZE_COL] = humanReadableSize(int(file_info[FileSystemModel.SIZE_COL]))
			
			self.append(file_info)
			
		for dir, dir_info in dir_node.getDirectories():
			dir_info.insert(FileSystemModel.ICON_COL, gtk.STOCK_DIRECTORY)
		
			dir_info[FileSystemModel.SIZE_COL] = humanReadableSize(int(dir_info[FileSystemModel.SIZE_COL]))
			
			self.append(dir_info)
			
		# Add ".." directory
		self.append([ 'd', gtk.STOCK_DIRECTORY, '..', '', ''])

	def findDirectory(self, path):
		"""Find the DirectoryNode object for the given path.
		
		Returns: DirectoryNode object
		"""
		self.dir_tree_lock.acquire()
		cur_node = self.dir_tree
		
		for dir in path.split('\\'):
			if len(dir) == 0:
				continue
			print 'findDirectory(): dir = ', dir
			cur_node, node_info = cur_node.getDirectory(dir)
			if cur_node == None:
				break
		self.dir_tree_lock.release()

		return cur_node
				
	def freeSpace(self):
		"""Get amount of free space available on PVR hard disk.
		"""
		try:
			total, free = self.puppy.getDiskSpace()
			self.freespace = free
		except:
			pass

		return humanReadableSize(self.freespace)

	def scanDirectory(self, dir):
		"""Recursively scan a directory for all subdirectories and files.
		
		This function recursivley scans the given directory for all subdirectories
		and files. Each subdirectory and file is stored in the DirectoryNode object.
		Return: DirectoryNode object representing the directory
		"""
		dir_node = DirectoryNode(dir.split('\\')[-1])
		pvr_files = self.puppy.listDir(dir)
		
		for file in pvr_files:
			if file[0] == 'd':
				if file[1] != '..':
					dir_node.addDirectory(self.scanDirectory(dir + '\\' + file[1]), file)
			else:
				dir_node.addFile(file[1], file)

		return dir_node
	
	def updateCache(self):
		"""Update the PVR file system cache.
		
		This function scans the entire PVR file system and creates a tree
		representing all the files and directories.
		"""
		if DEBUG:
			print 'Start updateCache()'
			
		self.dir_tree_lock.acquire()

		new_dir_tree = None

		# Attempt to update cache twice in case puppy was busy the first time
		for i in xrange(2):
			try:
				new_dir_tree = self.scanDirectory('')
			except puppy.PuppyBusyError:
				print 'updateCache(): Exception: PuppyBusyError'
				# Sleep for 1 second before trying again
				time.sleep(1)

		# Failed to update cache. Use existing cache.
		if new_dir_tree == None:
			new_dir_tree = self.dir_tree
			
		self.dir_tree = new_dir_tree

		self.dir_tree_lock.release()
		
		if DEBUG:
			print 'End updateCache()'

class DirectoryNode:
	def __init__(self, name):
		self.name = name
		self.sub_directories = {}
		self.files = []
		
	def addDirectory(self, dir, info):
		if DEBUG:
			print 'DirectoryNode[%s]: addDirectory(%s)' %(self.name, dir.name)
		self.sub_directories[dir.name] = (dir, info)
		
	# Add list of DictoryNodes
	def addDirectories(self, dirs):
		self.sub_directories += dirs
		
	def addFile(self, name, info):
		if DEBUG:
			print 'DirectoryNode[%s]: addFile(%s)' %(self.name, name)
		self.files.append((name, info))

	# Add list of files		
	def addFiles(self, files):
		self.files += files
		
	def getDirectory(self, dir):
		if DEBUG:
			print 'DirectoryNode[%s]: getDirectory(%s)' %(self.name, dir)
		try:
			return self.sub_directories[dir]
		except KeyError:
			return None
		
	def getDirectories(self):
		dir_list = []
		
		for name, (dir, dir_info) in self.sub_directories.items():
			dir_list.append((dir, copy.copy(dir_info)))
			
		return dir_list
		
	def getFiles(self):
		return copy.deepcopy(self.files)
		