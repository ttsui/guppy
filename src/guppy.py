#!/usr/bin/env python

## guppy.py - Main program
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

import sys
import os
import stat
import time
import string
import math
import threading
import Queue

import gtk
import gtk.glade
import gobject

import locale
import gettext

import puppy

APP_NAME = 'Guppy'
VERSION = '0.0.2'
AUTHORS = ['Tony Tsui tsui.tony@gmail.com']
WEBSITE = 'http://guppy.nongnu.org'
COPYRIGHT = 'Copyright (C) 2005 Tony Tsui'
LICENSE = 'GNU Public License'


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


class PVRFileSystemModel(FileSystemModel):
	dir_sep = '\\'
	def __init__(self):
		FileSystemModel.__init__(self)

		# FIXME: Get dir from when Guppy last exited
		self.current_dir = ''

		self.freespace = 0
				
		self.puppy = puppy.Puppy()
		
		self.changeDir()


	def changeDir(self, dir=None):
		if dir:
			# PVR root dir path is an empty string. Using '\' character does not
			# work.
			if dir == '\\':
				self.current_dir = ''
			elif len(self.current_dir) > 0 and self.current_dir[-1] != '\\':
				dir = self.current_dir + '\\' + dir
		else:
			dir = self.current_dir

		norm_path = os.path.normpath(dir.replace('\\', '/'))
		if norm_path != '.':
			dir = norm_path.replace('/', '\\')
		else:
			dir = ''

		# We can't get a listing during a file transfer
		try:
			pvr_files = self.puppy.listDir(dir)
		except puppy.PuppyBusyError:
			msg = _('Can not change directory during a file transfer')
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_INFO,
			                           buttons=gtk.BUTTONS_CLOSE,
			                           message_format=msg)
			response = dialog.run()
			dialog.destroy()

			return

		self.current_dir = dir
		
		# Clear model
		if len(self) > 0:
			self.clear()

		for file in pvr_files:
			# TODO: Set icon based on file type. Use dummy icon for now
			if file[FileSystemModel.TYPE_COL] == 'd':
				file.insert(FileSystemModel.ICON_COL, gtk.STOCK_DIRECTORY)
			else:				
				file.insert(FileSystemModel.ICON_COL, gtk.STOCK_FILE)
				
			file[FileSystemModel.SIZE_COL] = humanReadableSize(int(file[FileSystemModel.SIZE_COL]))
			self.append(file)
	
	def freeSpace(self):
		try:
			total, free = self.puppy.getDiskSpace()
			self.freespace = free
		except:
			pass

		return humanReadableSize(self.freespace)

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
			mode = os.stat(self.current_dir + '/' + file)

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
		cmd = 'df ' + self.current_dir
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
			
class GuppyWindow:
	FREE_SPACE_UPDATE_INTERVAL = 5000 # 5 secs
	
	def __init__(self):	
		# Find out proper way to find glade files
		guppy_glade_file = 'guppy.glade'

		self.initUIManager()		

		gtk.glade.set_custom_handler(self.customWidgetHandler)

		# Load glade file
		self.glade_xml = gtk.glade.XML(guppy_glade_file, None, gettext.textdomain())
		
		# Connect callback functions in glade file to functions
		self.glade_xml.signal_autoconnect(self)		
		
		accelgroup = self.uimanager.get_accel_group()
		window = self.glade_xml.get_widget('guppy_window')
		window.add_accel_group(accelgroup)
		
		self.puppy = puppy.Puppy()
		
		self.show_hidden = False

		self.pvr_total_size_label = self.glade_xml.get_widget('pvr_total_size_label')
		self.pvr_free_space_label = self.glade_xml.get_widget('pvr_free_space_label')

		self.pc_total_size_label = self.glade_xml.get_widget('pc_total_size_label')
		self.pc_free_space_label = self.glade_xml.get_widget('pc_free_space_label')
	
		self.pvr_model = PVRFileSystemModel()
		self.pc_model = PCFileSystemModel()
		
		self.free_space_timeout_id = gobject.timeout_add(GuppyWindow.FREE_SPACE_UPDATE_INTERVAL, self.update_free_space)

		# Queue to put files to be transferred. The transfer thread gets files
		# to transfer from this queue.
		self.transfer_queue = Queue.Queue(0)
		
		# Queue to put all files which has been transferred. Files on this queue
		# are removed when the Transfer Frame Clear button is clicked.
		self.transfer_complete_queue = Queue.Queue(0)
		
		# Create thread to transfer files
		self.transfer_thread = TransferThread(self)
		self.transfer_thread.setDaemon(True)
		self.transfer_thread.start()
	
		
	def initUIManager(self):
		self.uimanager = gtk.UIManager()
				
		actiongroup = gtk.ActionGroup('Actions')
		
		actiongroup.add_actions([('Quit', gtk.STOCK_QUIT, '_Quit', None, None, self.on_quit),
		                         ('File', None, '_File'),
		                         ('View', None, '_View'),
		                         ('Transfer', None, '_Transfer'),
		                         ('Help', None, '_Help'),
                                 ('About', gtk.STOCK_ABOUT , '_About', None, None, self.on_about)])

		# FIXME: Use a proper icon for Turbo button
		actiongroup.add_toggle_actions([('Turbo', gtk.STOCK_EXECUTE, 'Tur_bo', None, 'Turbo Transfer', self.on_turbo_toggled),
		                                ('ShowHidden', None, 'Show Hidden Files', None, 'Show hidden files', self.on_show_hidden_toggled),
		                                ('ShowFileTransfer', None, 'Show File Transfer', None, 'Show File Transfer', self.on_show_file_transfer_toggled)])

		# Create reference to ShowFileTransfer action so we can update the
		# toggle state accordingly when the transfer frame close button is
		# clicked.
		self.show_file_transfer_action = actiongroup.get_action('ShowFileTransfer')
		
		self.uimanager.insert_action_group(actiongroup, 0)
		
		# Create separate action group for upload so sensitivity can be set
		# according to selection in PC file tree
		self.upload_actiongrp = gtk.ActionGroup('UploadAction')                                 
		self.upload_actiongrp.add_actions([('Upload', gtk.STOCK_GO_BACK, '_Upload', None, 'Upload File', self.on_upload_btn_clicked)])
		self.upload_actiongrp.set_sensitive(False)
		self.uimanager.insert_action_group(self.upload_actiongrp, 1)

		# Create separate action group for download so sensitivity can be set
		# according to selection in PVR file tree
		self.download_actiongrp = gtk.ActionGroup('DownloadAction')                                 
		self.download_actiongrp.add_actions([('Download', gtk.STOCK_GO_FORWARD, '_Download', None, 'Download File', self.on_download_btn_clicked)])
		self.download_actiongrp.set_sensitive(False)
		self.uimanager.insert_action_group(self.download_actiongrp, 2)
		
		self.uimanager.add_ui_from_file('guppy-gtk.xml')

	
	def customWidgetHandler(self, glade, func_name, widget_name, str1, str2, int1, int2, *args):
		handler = getattr(self, func_name)
		return handler(str1, str2, int1, int2)
		

	def createFileTrees(self):	
		self.pvr_treeview = self.glade_xml.get_widget('pvr_treeview')	
		pvr_liststore = self.pvr_model.filter_new()
		pvr_liststore.set_visible_func(self.hiddenFileFilter)
		pvr_liststore = gtk.TreeModelSort(pvr_liststore)
		self.pvr_liststore = pvr_liststore

		self.pc_treeview = self.glade_xml.get_widget('pc_treeview')	
		pc_liststore = self.pc_model.filter_new()
		pc_liststore.set_visible_func(self.hiddenFileFilter)
		pc_liststore = gtk.TreeModelSort(pc_liststore)
		self.pc_liststore = pc_liststore
		
		self.pvr_path_entry = self.glade_xml.get_widget('pvr_path_entry')
		self.pc_path_entry = self.glade_xml.get_widget('pc_path_entry')
		
		self.pvr_path_entry.connect('activate', self.on_path_entry_activate, self.pvr_model)
		self.pc_path_entry.connect('activate', self.on_path_entry_activate, self.pc_model)
		
		self.pvr_path_entry.set_text(self.pvr_model.getCWD())
		self.pc_path_entry.set_text(self.pc_model.getCWD())
		
		for treeview, liststore in (self.pvr_treeview, pvr_liststore), (self.pc_treeview, pc_liststore):
			treeview.set_model(liststore)
			fs_model = liststore.get_model().get_model()

			sort_func = fs_model.sort_func
			liststore.set_default_sort_func(sort_func, FileSystemModel.NAME_COL)

			treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
			
			treeview.connect('row-activated', self.on_treeview_row_activated, fs_model)
			handler_id = treeview.get_selection().connect('changed', self.on_treeview_changed, fs_model)
			treeview.set_data('changed_handler_id', handler_id)
			
			text_cell = gtk.CellRendererText()
			pixb_cell = gtk.CellRendererPixbuf()
			
			col = gtk.TreeViewColumn(_('Name'))
			col.pack_start(pixb_cell, False)
			col.pack_start(text_cell, True)
			col.set_attributes(text_cell, text=FileSystemModel.NAME_COL)
			col.set_attributes(pixb_cell, stock_id=FileSystemModel.ICON_COL)
			col.set_clickable(True)
			col.set_sort_indicator(True)
			col.set_sort_column_id(FileSystemModel.NAME_COL)
			treeview.append_column(col)
			liststore.set_sort_func(FileSystemModel.NAME_COL, sort_func, FileSystemModel.NAME_COL)
						
			col = gtk.TreeViewColumn(_('Date'), text_cell, text=FileSystemModel.DATE_COL)
			col.set_clickable(True)
			col.set_sort_indicator(True)
			col.set_sort_column_id(FileSystemModel.DATE_COL)
			treeview.append_column(col)
			liststore.set_sort_func(FileSystemModel.DATE_COL, sort_func, FileSystemModel.DATE_COL)
				
			col = gtk.TreeViewColumn(_('Size'), text_cell, text=FileSystemModel.SIZE_COL)
			col.set_clickable(True)
			col.set_sort_indicator(True)
			col.set_sort_column_id(FileSystemModel.SIZE_COL)
			treeview.append_column(col)
			liststore.set_sort_func(FileSystemModel.SIZE_COL, sort_func, FileSystemModel.SIZE_COL)

		
	def createMenuBar(self, str1, str2, int1, int2, *args):
		return self.uimanager.get_widget('/MenuBar')
		
	def createToolbar(self, str1, str2, int1, int2, *args):
		toolbar = self.uimanager.get_widget('/Toolbar')
		toolbar.set_orientation(gtk.ORIENTATION_VERTICAL)
		return toolbar
			
	def hiddenFileFilter(self, model, iter, data=None):
		name = model.get_value(iter, FileSystemModel.NAME_COL)
		if self.show_hidden == False and (name == None or (name[0] == '.' and name[1] != '.')):
			return False
		
		return True
	
	def run(self):
		self.createFileTrees()
		gtk.gdk.threads_enter()
		gtk.main()
		gtk.gdk.threads_leave()


	def on_about(self, widget, data=None):	
		dialog = gtk.AboutDialog()
		dialog.set_name(APP_NAME)
		dialog.set_authors(AUTHORS)
		dialog.set_copyright(COPYRIGHT)
		dialog.set_version(VERSION)
		dialog.set_license(LICENSE)
		dialog.set_website(WEBSITE)
		dialog.show()
	
	def on_column_clicked(self, col, data):
		order = col.get_sort_order()
		print order
		if order == gtk.SORT_ASCENDING:
			print 'foo'
			order = gtk.SORT_DESCENDING
		else:
			print 'bar'
			order = gtk.SORT_ASCENDING

		col.set_sort_order(order)
		data[0].set_sort_column_id(data[1], order)
	
	def on_download_btn_clicked(self, widget, data=None):
		self.transferFile('download')

	def on_guppy_window_delete_event(self, widget, event, data=None):
		self.on_quit(widget, data)
		
	def on_path_entry_activate(self, widget, fs_model):
		fs_model.changeDir(widget.get_text())
		
	def on_quit(self, widget, data=None):
		gtk.main_quit()
		self.puppy.cancelTransfer()
		
	def on_show_file_transfer_toggled(self, widget, data=None):
		transfer_frame = self.glade_xml.get_widget('transfer_frame')
		if not transfer_frame.get_property('visible'):
			self.show_transfer_frame()
		else:
			transfer_frame.hide()
					
	def on_show_hidden_toggled(self, widget, data=None):
		self.show_hidden = not self.show_hidden
		self.pc_liststore.get_model().refilter()
		self.pvr_liststore.get_model().refilter()

	def on_treeview_changed(self, widget, fs_model):
		model, files = widget.get_selected_rows()
		
		file_no = 1
		file_count = len(files)
		total_size = 0
		for path in files:
			iter = model.get_iter(path)
			type = model.get_value(iter, FileSystemModel.TYPE_COL)
			
			size = model.get_value(iter, FileSystemModel.SIZE_COL)
			if type != 'd':
				total_size += convertToBytes(size)

		if total_size > 0:
			msg = _('Selection Size') + ': ' + humanReadableSize(total_size)
		else:
			msg = _('Selection Size') + ':'
		
		if isinstance(fs_model, PCFileSystemModel):
			label = self.pc_total_size_label
			actiongrp = self.upload_actiongrp
		else:
			label = self.pvr_total_size_label
			actiongrp = self.download_actiongrp
			
		label.set_text(msg)
		if total_size > 0:
			actiongrp.set_sensitive(True)
		else:
			actiongrp.set_sensitive(False)
	
	def on_treeview_row_activated(self, widget, path, col, fs_model):
		model = widget.get_model()
		iter = model.get_iter(path)
		name = model.get_value(iter, FileSystemModel.NAME_COL)
		type = model.get_value(iter, FileSystemModel.TYPE_COL)
		
		if type == 'd':
			fs_model.changeDir(name)
			path = fs_model.getCWD()
			if isinstance(fs_model, PCFileSystemModel):
				self.pc_path_entry.set_text(path)
			else:
				self.pvr_path_entry.set_text(path)
			
	def on_turbo_toggled(self, widget, data=None):
		self.puppy.setTurbo(widget.get_active())
		
	def on_upload_btn_clicked(self, widget, data=None):
		self.transferFile('upload')

	def on_transfer_clear_btn_clicked(self, widget, data=None):
		# Loop until we get a Queue.Empty exception
		while True:
			try:
				file_transfer = self.transfer_complete_queue.get_nowait()
			except Queue.Empty:
				break

			progress_box = file_transfer.xml.get_widget('progress_box')
			# progress_box may be None if the Remove button was clicked on it
			if progress_box:
				progress_box.destroy()
	
	def on_transfer_close_btn_clicked(self, widget, data=None):
		self.show_file_transfer_action.set_active(False)
		self.on_show_file_transfer_toggled(widget)

	def on_transfer_remove_btn_clicked(self, widget, file_transfer):
		file_transfer.cancel()
		
		progress_box = file_transfer.xml.get_widget('progress_box')
		progress_box.destroy()

	def on_transfer_stop_btn_clicked(self, widget, data=None):
		self.puppy.cancelTransfer()

	
	def show_transfer_frame(self):
		# Set position of pane separator
		# Give progress frame height of 180 pixels. This should be enough room
		# to show two file transfers.
		vpane = self.glade_xml.get_widget('vpane')
		vpane.set_position(vpane.get_allocation().height - 185)
		
		transfer_frame = self.glade_xml.get_widget('transfer_frame')
		transfer_frame.show()
		
	def transferFile(self, direction):
		if direction == 'download':
			model, files = self.pvr_treeview.get_selection().get_selected_rows()
			direction_text = _('Downloading')
			selection_size = self.pvr_total_size_label.get_text().split(':')[1]
			free_space = self.pc_model.freeSpace()
		else:
			model, files = self.pc_treeview.get_selection().get_selected_rows()
			direction_text = _('Uploading')
			selection_size = self.pc_total_size_label.get_text().split(':')[1]
			free_space = self.pvr_model.freeSpace()

		# Check for enough free disk space
		selection_size = convertToBytes(selection_size)
		free_space = convertToBytes(free_space)

		if selection_size > free_space:
			msg = _('Not enough disk space available on your')
			if direction == 'download':
				msg += ' ' + _('PC')
			else:
				msg += ' ' + _('PVR')
			msg += '.\n'
			msg += _('Do you still want to continue transfer?')	
			
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
			                           buttons=gtk.BUTTONS_YES_NO,
			                           message_format=msg)
			response = dialog.run()
			dialog.destroy()
			if response == gtk.RESPONSE_NO or response == gtk.RESPONSE_DELETE_EVENT:
				return

		queue_box = self.glade_xml.get_widget('queue_vbox')
		self.show_transfer_frame()

		file_count = len(files)
		file_no = 1
		for path in files:
			iter = model.get_iter(path)
			file = model.get_value(iter, FileSystemModel.NAME_COL)

			if direction == 'download':
				src_dir = self.pvr_model.getCWD()
				dst_dir = self.pc_model.getCWD()
				src_file = src_dir + '\\' + file
				dst_file = dst_dir + '/' + file
				existing_file = os.access(dst_file, os.F_OK)
			else:
				src_dir = self.pc_model.getCWD()
				dst_dir = self.pvr_model.getCWD()
				src_file = src_dir + '/' + file
				dst_file = dst_dir + '\\' + file
				existing_file = self.pvr_model.find(file)

			if existing_file:
				msg = _('The file') + ' "' + dst_file + '" ' + _('already exists. Would you like to replace it?')
				msg2 = _('If you replace an existing file, its contents will be overwritten.')
				dialog = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
				                           buttons=gtk.BUTTONS_YES_NO,
				                           message_format=msg)
				response = dialog.run()
				dialog.destroy()

				if response == gtk.RESPONSE_NO or response == gtk.RESPONSE_DELETE_EVENT:
					file_no += 1
					continue

			xml = gtk.glade.XML('guppy.glade', 'progress_box')
			xml.signal_autoconnect(self)		

			progress_box = xml.get_widget('progress_box')
			
			file_label = xml.get_widget('transfer_file_label')
			from_label = xml.get_widget('transfer_from_label')
			to_label = xml.get_widget('transfer_to_label')
	
			dir_label = xml.get_widget('transfer_direction_label')
			dir_label.set_markup('<b>' + direction_text + ':</b>')
	
			file_label.set_text(file)
			from_label.set_text(src_dir)
			to_label.set_text(dst_dir)

			queue_box.pack_start(progress_box, expand=False)
	
			file_transfer = FileTransfer(direction, src_file, dst_file, xml)

			# Connect transfer instance remove button signal handler
			remove_btn = xml.get_widget('transfer_remove_button')
			remove_btn.connect('clicked', self.on_transfer_remove_btn_clicked, file_transfer)

			self.transfer_queue.put(file_transfer, True, None)


	def update_treeviews(self):		
		# Update FileSystemModel view				
		models = [ (self.pc_model, self.pc_treeview), (self.pvr_model, self.pvr_treeview) ]
		for model, treeview in models:
			handler_id = treeview.get_data('changed_handler_id')
			selection = treeview.get_selection()
			selected_rows = selection.get_selected_rows()
			selection.handler_block(handler_id)
			model.changeDir()
			selection.handler_unblock(handler_id)
			for path in selected_rows[1]:
				selection.select_path(path)
			
	def update_free_space(self):
		self.pvr_free_space_label.set_text(_('Free Space') + ': ' + self.pvr_model.freeSpace())
		self.pc_free_space_label.set_text(_('Free Space') + ': ' + self.pc_model.freeSpace())
		return True


		
class FileTransfer:
	def __init__(self, direction, src, dst, xml):
		self.direction = direction
		self.src = src
		self.dst = dst
		self.xml = xml
		
		self.alive = True
	
	def isAlive(self):
		return self.alive
		
	def cancel(self):
		self.alive = False
	
	def complete(self):
		self.alive = False
		
class TransferThread(threading.Thread):
	NUM_OF_RESET_ATTEMPTS = 6
	NUM_OF_TRANSFER_ATTEMPTS = 2
	
	def __init__(self, guppy):
		threading.Thread.__init__(self)
		self.guppy = guppy
		self.file_queue = self.guppy.transfer_queue
		self.complete_queue = self.guppy.transfer_complete_queue

	def run(self):
		while True:
			file_transfer = self.file_queue.get(True, None)
			if not file_transfer.isAlive():
				continue
				
			direction = file_transfer.direction
			src_file = file_transfer.src
			dst_file = file_transfer.dst
			xml = file_transfer.xml
			
			# Make all widgets in progress box active
			for widget in ['progress_hbox1', 'progress_hbox2']:
				widget = xml.get_widget(widget)
				gtk.gdk.threads_enter()
				widget.set_sensitive(True)
				gtk.gdk.threads_leave()
		
			remove_btn = xml.get_widget('transfer_remove_button')	
			gtk.gdk.threads_enter()
			remove_btn.hide()
			gtk.gdk.threads_leave()
			
			stop_btn = xml.get_widget('transfer_stop_button')	
			gtk.gdk.threads_enter()
			stop_btn.show()
			gtk.gdk.threads_leave()

			# Set width of Stop button to be the same as Remove button
			gtk.gdk.threads_enter()
			allocation = remove_btn.get_allocation()
			gtk.gdk.threads_leave()
			gtk.gdk.threads_enter()
			stop_btn.set_size_request(allocation.width, allocation.height)
			gtk.gdk.threads_leave()

			progress_bar = xml.get_widget('transfer_progressbar')
			
			if direction == 'download':
				self.guppy.puppy.getFile(src_file, dst_file)
			else:
				self.guppy.puppy.putFile(src_file, dst_file)

			transfer_successful = True
			transfer_attempt = 1
			percent = True			
			while percent != None:
				try:
					percent, speed, time = self.guppy.puppy.getProgress()
				except puppy.PuppyError:
					# Quit trying to transfer file after a certain number of attempts
					if transfer_attempt > TransferThread.NUM_OF_TRANSFER_ATTEMPTS:
						transfer_successful = False
						break
					
					transfer_attempt += 1

					# Try to reset PVR before attempt transfer again
					reset_successful = False
					attempts = 0
					while not reset_successful and attempts < TransferThread.NUM_OF_RESET_ATTEMPTS:
						reset_successful = self.guppy.puppy.reset()
						attempts += 1

					if direction == 'download':
						self.guppy.puppy.getFile(src_file, dst_file)
					else:
						self.guppy.puppy.putFile(src_file, dst_file)

					continue

				# Transfer may have completed
				if percent is None:
					break
					
				gtk.gdk.threads_enter()
				progress_bar.set_fraction(float(percent)/100)
				gtk.gdk.threads_leave()
				
				gtk.gdk.threads_enter()
				progress_bar.set_text('(' + time['remaining'] + ' ' + _('Remaining') + ')')
				gtk.gdk.threads_leave()
				
				gtk.gdk.threads_enter()
				while gtk.events_pending():
					gtk.main_iteration()
				gtk.gdk.threads_leave()
			
			if transfer_successful:
				gtk.gdk.threads_enter()
				progress_bar.set_fraction(1)
				gtk.gdk.threads_leave()
				
				gtk.gdk.threads_enter()
				progress_bar.set_text(_('Finished'))
				gtk.gdk.threads_leave()
			else:
				gtk.gdk.threads_enter()
				progress_bar.set_text(_('Transfer Failed'))
				gtk.gdk.threads_leave()
				

			# Insensitise all widgets			
			for widget in ['progress_hbox1', 'progress_hbox2']:
				widget = xml.get_widget(widget)
				gtk.gdk.threads_enter()
				widget.set_sensitive(False)
				gtk.gdk.threads_leave()

			# Swap Stop button for Remove button
			gtk.gdk.threads_enter()
			stop_btn.hide()
			gtk.gdk.threads_leave()
			
			gtk.gdk.threads_enter()
			remove_btn.show()
			gtk.gdk.threads_leave()

			file_transfer.complete()
			
			# Update file treeviews
			gtk.gdk.threads_enter()
			self.guppy.update_treeviews()
			gtk.gdk.threads_leave()
			
			# Put on queue for completed transfers
			self.complete_queue.put(file_transfer)

if __name__ == "__main__":
	locale.setlocale(locale.LC_ALL, '')
	gettext.bindtextdomain(APP_NAME, 'i18n')
	gettext.textdomain(APP_NAME)
	gettext.install(APP_NAME, 'i18n', unicode=1)
	
	gtk.gdk.threads_init()
	guppy = GuppyWindow()
	guppy.run()
