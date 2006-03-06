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

from puppy import *
from util import *

# Set to True for debug output
DEBUG = False

class FileSystemModel(gtk.ListStore):
	TYPE_COL, ICON_COL, NAME_COL, DATE_COL, SIZE_COL = range(5)
	LIST_TYPES = []
	LIST_TYPES.insert(TYPE_COL, gobject.TYPE_STRING)
	LIST_TYPES.insert(ICON_COL, gtk.gdk.Pixbuf)
	LIST_TYPES.insert(NAME_COL, gobject.TYPE_STRING)
	LIST_TYPES.insert(DATE_COL, gobject.TYPE_STRING)
	LIST_TYPES.insert(SIZE_COL, gobject.TYPE_STRING)

	icons_loaded = False

	# Set in FileSystemModel::load_icons()
	file_icon = None
	dir_icon = None
	# Also set in FileSystemModel::__init__() if not in theme
	video_icon = None
	audio_icon = None
	
	icon_theme = gtk.icon_theme_get_default()
	theme_change_callback = []
	
	@staticmethod
	def __connect_theme_change_callback(callback):
		print '__connect_theme_change_callback()'
		FileSystemModel.theme_change_callback.append(callback)
		
	@staticmethod
	def __load_icons(icon_theme, datadir):
		print 'load_icons()'
		
		if not FileSystemModel.icons_loaded:
			print 'connect icon theme change'
			icon_theme.connect('changed', FileSystemModel.__load_icons, datadir)
		
		img = gtk.Image()
		FileSystemModel.file_icon = img.render_icon(gtk.STOCK_FILE,
		                                            gtk.ICON_SIZE_LARGE_TOOLBAR)
	
		settings = gtk.settings_get_for_screen(img.get_screen())
		icon_size = gtk.icon_size_lookup_for_settings(settings,
		                                            gtk.ICON_SIZE_LARGE_TOOLBAR)
		if icon_size:
			icon_size = max(icon_size[0], icon_size[1])
		else:
			icon_size = 24

		# List of icons and corresponding icon theme name
		icons = { 'dir_icon' : 'folder',
		          'video_icon' : 'video-x-generic',
		          'audio_icon' : 'audio-x-generic'}
	
		# Try and load icon from icon theme	
		for key, icon_name in icons.iteritems():
			try:
				icons[key] = icon_theme.load_icon(icon_name, icon_size,
				                                  gtk.ICON_LOOKUP_USE_BUILTIN)
			except gobject.GError, exc:
				icons[key] = None
				pass

		FileSystemModel.dir_icon = icons['dir_icon']
		FileSystemModel.video_icon = icons['video_icon']
		FileSystemModel.audio_icon = icons['audio_icon']

		if FileSystemModel.dir_icon == None:
			FileSystemModel.dir_icon = img.render_icon(gtk.STOCK_DIRECTORY,
		                                               gtk.ICON_SIZE_LARGE_TOOLBAR)
		
		if FileSystemModel.video_icon == None:	
			FileSystemModel.video_icon = gtk.gdk.pixbuf_new_from_file(datadir +
			                                                  '/' + 'video.png')

		if FileSystemModel.audio_icon == None:	
			FileSystemModel.audio_icon = gtk.gdk.pixbuf_new_from_file(datadir +
			                                                  '/' + 'audio.png')
		
		if FileSystemModel.icons_loaded:
			for callback in FileSystemModel.theme_change_callback:
				print 'callback = ', callback
				callback()
		
		FileSystemModel.icons_loaded = True
	
	def __init__(self, datadir, show_parent_dir=False):
		self.current_dir = None
		self.show_parent_dir = show_parent_dir
		gtk.ListStore.__init__(self, FileSystemModel.LIST_TYPES[FileSystemModel.TYPE_COL],
							   FileSystemModel.LIST_TYPES[FileSystemModel.ICON_COL],
		                       FileSystemModel.LIST_TYPES[FileSystemModel.NAME_COL],
							   FileSystemModel.LIST_TYPES[FileSystemModel.DATE_COL],
			                   FileSystemModel.LIST_TYPES[FileSystemModel.SIZE_COL])

		if not FileSystemModel.icons_loaded:
			FileSystemModel.__load_icons(FileSystemModel.icon_theme, datadir)
		FileSystemModel.__connect_theme_change_callback(self.changeDir)

	def abspath(self, file):
		if self.current_dir[-1] != self.slash and file[0] != self.slash:
			return self.current_dir + self.slash + file
		else:
			return self.current_dir + file
		
	def find(self, name):
		for row in self:
			if name == row[FileSystemModel.NAME_COL]:
				return row
				
		return None

	def mkdir(self):
		name = 'untitled folder'
		name_count = 1
		
		while self.exists(name):
			name = 'untitled folder ' + str(name_count)
			name_count += 1
			
		return name
				
	def getCWD(self):
		return self.current_dir
	
	def rename(self, old, new, overwrite=False):
		if old == new:
			return
		
		if not overwrite and self.exists(new):
			raise os.error('[Errno 17] File exists')
		
		if DEBUG:
			print 'renaming: ', self.abspath(old), ' to ', self.abspath(new)
		
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
		if date1_str == None or len(date1_str) == 0:
			return -1
		
		date2_str = model.get_value(iter2, col)
		if date2_str == None or len(date2_str) == 0:
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
		size1 = model.get_value(iter1, col)
		size2 = model.get_value(iter2, col)

		# We can get None on PVR FS.
		if size1 == None and size2 != None:
			return -1
		elif size1 != None and size2 == None:
			return 1
		elif size1 == None and size2 == None:
			return self.string_sort_func(model, iter1, iter2, FileSystemModel.NAME_COL);

		# Handle when size is empty string. Typical for directories on PC.			
		size1_len = len(size1)
		size2_len = len(size2)

		if size1_len == 0 and size2_len > 0:
			return -1
		elif size1_len > 0 and size2_len == 0:
			return 1
		elif size1_len == 0 and size2_len == 0:
			return self.string_sort_func(model, iter1, iter2, FileSystemModel.NAME_COL);
		
		size1 = size1.split()
		size2 = size2.split()

		unit_weight = { 'B' : 1, 'KB' : 2, 'MB' : 3, 'GB' : 4 }

		# Sizes in bytes may not have 'B' unit
		if len(size1) < 2:
			size1[1] = unit_weight['B']
		else:
			size1[1] = unit_weight[size1[1]]

		# Sizes in bytes may not have 'B' unit
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
	def __init__(self, datadir, show_parent_dir=False):
		FileSystemModel.__init__(self, datadir, show_parent_dir)
		
		# FIXME: Get dir from when Guppy last exited
		self.current_dir = os.environ['HOME']
		
		self.slash = '/'
		
	def changeDir(self, dir=None):
		if dir:
			# Append CWD if dir is not an absolute path
			if dir[0] != self.slash:
				dir = self.abspath(dir)
		else:
			dir = self.current_dir

		dir = os.path.normpath(dir)
		# os.path.normpath() doesn't normalise '//' to '/'
		if dir == '//':
			dir = self.slash
		
		if not os.access(dir, os.F_OK):
			return False

		self.current_dir = dir
			
		if len(self) > 0:
			self.clear()
		
		# Parent directory
		if self.show_parent_dir:
			self.append(['d', gtk.STOCK_DIRECTORY, '..', '', ''])

		for file in os.listdir(self.current_dir):
			try:
				mode = os.stat(self.abspath(file))
			except OSError, (errno, strerror):
				print 'PCFileSystemModel::changeDir(%s): OSError(%s): %s\n' % (self.abspath(file), errno, strerror)
				continue

			if stat.S_ISDIR(mode[stat.ST_MODE]):
				type = 'd'
				icon = self.dir_icon
				size = ''
			else:
				type = 'f'
				if file[-4:].lower() == '.rec':
					icon = FileSystemModel.video_icon
				elif file[-4:].lower() == '.mp3':
					icon = FileSystemModel.audio_icon
				else:
					icon = FileSystemModel.file_icon
				size = humanReadableSize(mode[stat.ST_SIZE])
			
			mtime = time.strftime('%a %b %d %Y', time.localtime(mode[stat.ST_MTIME]))
			entry = [ type, icon, file, mtime, size ]
			self.append(entry)

		return True
	
	def delete(self, file):
		path = self.abspath(file)
		
		mode = os.stat(path)
		if stat.S_ISDIR(mode[stat.ST_MODE]):
			import shutil
			shutil.rmtree(path)
		else:
			os.remove(path)
		
	def exists(self, file):
		return os.access(self.abspath(file), os.F_OK)
		
	def freeSpace(self):
		cmd = 'df -P ' + '"' + self.current_dir + '"'
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

	def mkdir(self):
		name = FileSystemModel.mkdir(self)
			
		if DEBUG:
			print 'making directory: ', self.abspath(name)
		
		os.mkdir(self.abspath(name))
		
		return name
		
	def rename(self, old, new, overwrite=False):
		try:
			FileSystemModel.rename(self, old, new)
		except OSError:
			# Update model to ensure the latest files in the current
			# is visble.
			self.changeDir()
			raise
		
		os.rename(self.abspath(old), self.abspath(new))

class PVRFileSystemModel(FileSystemModel):
	def __init__(self, datadir, show_parent_dir=False):
		FileSystemModel.__init__(self, datadir, show_parent_dir)

		self.slash = '\\'
		# FIXME: Get dir from when Guppy last exited
		# We need to use an empty string to list the PVR root directory.
		self.current_dir = self.slash

		self.freespace = 0
				
		self.puppy = Puppy()

		self.dir_tree_lock = threading.Lock()

		self.dir_tree = None
		

	def changeDir(self, dir=None):
		"""Change directory and update model data accordingly.
		"""
		if dir:
			# Append CWD if dir is not an absolute path
			if dir[0] != self.slash:
				dir = self.abspath(dir)
		else:
			dir = self.current_dir

		norm_path = os.path.normpath(dir.replace(self.slash, '/'))
		# norm_path is '.' when _dir_ is an empty string. _dir_ is an empty
		# string for the PVR root directory.
		# Also don't change dir when changing to '..' directory.
		if norm_path == '.' or norm_path == '..':
			dir = self.slash
		else:
			dir = norm_path.replace('/', self.slash)

		dir_node = self.findDirectory(dir)
		if dir_node == None:
			return
		
		self.current_dir = dir

		# Clear model
		if len(self) > 0:
			self.clear()

		for file_name, file_info in dir_node.getFiles():
			if file_name[-4:].lower() == '.rec':
				icon = FileSystemModel.video_icon		
			elif file_name[-4:].lower() == '.mp3':
				icon = FileSystemModel.audio_icon		
			else:
				icon = FileSystemModel.file_icon
				
			file_info.insert(FileSystemModel.ICON_COL, icon)
		
			file_info[FileSystemModel.SIZE_COL] = humanReadableSize(int(file_info[FileSystemModel.SIZE_COL]))
			
			self.append(file_info)
			
		for dir, dir_info in dir_node.getDirectories():
			dir_info.insert(FileSystemModel.ICON_COL, FileSystemModel.dir_icon)
			
			dir_info[FileSystemModel.SIZE_COL] = humanReadableSize(int(dir_info[FileSystemModel.SIZE_COL]))
			
			self.append(dir_info)
			
		# Add ".." directory
		if self.show_parent_dir:
			self.append([ 'd', gtk.STOCK_DIRECTORY, '..', '', ''])

	def delete(self, file):
		self.puppy.delete(self.abspath(file))

	def exists(self, file):
		pvr_files = self.puppy.listDir(self.current_dir)
		
		for p_file in pvr_files:
			if p_file[1] == file:
				return True
			
		return False
	
	def findDirectory(self, path):
		"""Find the DirectoryNode object for the given path.
		
		Returns: DirectoryNode object
		"""
		self.dir_tree_lock.acquire()
		cur_node = self.dir_tree
		
		# Strip trailing slash
		path = path.rstrip(self.slash)
		
		for dir in path.split(self.slash):
			if len(dir) == 0:
				continue
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
		except PuppyBusyError:
			pass

		return humanReadableSize(self.freespace)

	def mkdir(self):
		name = FileSystemModel.mkdir(self)
			
		if DEBUG:
			print 'making directory: ', self.abspath(name)
		self.puppy.makeDir(self.abspath(name))
		
	def rename(self, old, new, overwrite=False):
		try:
			FileSystemModel.rename(self, old, new)
		except OSError:
			# Update model to ensure the latest files in the current
			# is visble.
			self.updateCache()
			self.changeDir()
			raise
		
		self.puppy.rename(self.abspath(old), self.abspath(new))
		
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
			except PuppyBusyError:
				# Sleep for 1 second before trying again
				time.sleep(1)
				continue
			except PuppyError:
				self.dir_tree_lock.release()
				raise
			break

		# Failed to update cache. Use existing cache.
		if new_dir_tree == None:
			new_dir_tree = self.dir_tree
			
		self.dir_tree = new_dir_tree

		self.dir_tree_lock.release()
		
		if DEBUG:
			print 'End updateCache()'

	def updateDirectory(self, dir):
		"""Update the directory node in the directory tree.
		
		"""
		if DEBUG:
			print 'Start updateDirectory(%s)' % (dir)
			
		# Strip trailing slash
		dir = dir.rstrip(self.slash)

		self.dir_tree_lock.acquire()

		# Call scanDirectory() directly if dir is root dir, i.e. '\'
		if len(dir) == 0:
			self.dir_tree = self.scanDirectory('')
			self.dir_tree_lock.release()
			if DEBUG:
				print 'End updateDirectory(\\)'
			return

		# Get components of directory path as a list
		path = dir.split('\\')

		# Find parent node		
		parent_node = self.dir_tree
		for name in path[:-1]:
			if len(name) == 0:
				continue
			par_node, node_info = parent_node.getDirectory(name)
			if parent_node == None:
				break
				
		cur_node, node_info = parent_node.getDirectory(path[-1])
		
		new_node = None
		# Attempt to update cache twice in case puppy was busy the first time
		for i in xrange(2):
			try:
				new_node = self.scanDirectory(dir)
			except PuppyBusyError:
				# Sleep for 1 second before trying again
				time.sleep(1)
				continue
			except PuppyError:
				self.dir_tree_lock.release()
				raise
			break

		# Failed to update cache. Use existing node.
		if new_node == None:
			new_node = cur_node

		# Replace wit new node
		parent_node.addDirectory(new_node, node_info)
		
		self.dir_tree_lock.release()
		
		if DEBUG:
			print 'End updateDirectory()'
		

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
		
	def print_tree(self):
		print '\t' + self.name
		for node, info in self.sub_directories.itervalues():
			node.print_tree()
			
		for file in self.files:
			print file
