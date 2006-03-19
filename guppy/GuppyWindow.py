## GuppyWindow.py - Main Window
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
import os
import stat
import threading
import Queue
import time

import gtk
import gtk.glade
import gobject
import pango

import locale
import gettext

from puppy import *
from FileSystemModel import *
from util import *
from about import *

class GuppyWindow:
	SCREEN_INFO_UPDATE_INTERVAL = 10 * 60 * 1000 # 10 mins (unit in milliseconds)
	
	# Quit command to put on transfer queue
	QUIT_CMD = 'Quit'
	
	def __init__(self, datadir=''):	
		# The PathBar widget only works with PyGtk 2.8 and greater
		major, minor, micro = gtk.pygtk_version
		if major <= 2 and minor < 8:
			self.no_path_bar_support = True
		else:
			self.no_path_bar_support = False
	
		# Initialise Gtk thread support
		gtk.gdk.threads_init()

		self.datadir = datadir

		# Find out proper way to find glade files
		self.glade_file = self.datadir + '/' + 'guppy.glade'

		self.pvr_error_window = PVRErrorWindow(self.glade_file)

		actions = self.initUIManager()

		# This must be done before loading the glade file.
		gtk.glade.set_custom_handler(self.customWidgetHandler)
		
		# Load glade file
		self.glade_xml = gtk.glade.XML(self.glade_file, None, gettext.textdomain())
		
		# Connect callback functions in glade file to functions
		self.glade_xml.signal_autoconnect(self)
		
		# Connect buttons in toolbar to their respective action
		for action, widget in [ (actions['turbo'], 'turbo_btn'),
		                (actions['upload'], 'upload_btn'),
						(actions['download'], 'download_btn') ]:
			btn = self.glade_xml.get_widget(widget)
			action.connect_proxy(btn)
		
		accelgroup = self.uimanager.get_accel_group()
		window = self.glade_xml.get_widget('guppy_window')
		window.add_accel_group(accelgroup)

		self.puppy = Puppy()
		
		self.show_hidden = False

		self.pvr_error_btn = self.glade_xml.get_widget('pvr_error_btn')
		
		self.pvr_total_size_label = self.glade_xml.get_widget('pvr_total_size_label')
		self.pvr_free_space_label = self.glade_xml.get_widget('pvr_free_space_label')

		self.pc_total_size_label = self.glade_xml.get_widget('pc_total_size_label')
		self.pc_free_space_label = self.glade_xml.get_widget('pc_free_space_label')
	
		if self.no_path_bar_support:
			show_parent_dir = True
		else:
			show_parent_dir = False

		self.pvr_model = PVRFileSystemModel(self.datadir, show_parent_dir)
		self.pc_model = PCFileSystemModel(self.datadir, show_parent_dir)
		
		self.pc_path_entry_box = self.glade_xml.get_widget('pc_path_entry_box')
		self.pvr_path_entry_box = self.glade_xml.get_widget('pvr_path_entry_box')
		
		self.pc_path_bar = None
		self.pvr_path_bar = None
		if self.no_path_bar_support:
			self.pc_path_entry_box.show()
			self.pvr_path_entry_box.show()
		else:
			self.pvr_path_bar = PathBar(self, 'pvr')
			self.pvr_path_bar.set_border_width(3)
			
			self.pc_path_bar = PathBar(self, 'pc')
			self.pc_path_bar.set_border_width(3)
			
			pvr_vbox = self.glade_xml.get_widget('pvr_path_vbox')
			pvr_vbox.pack_start(self.pvr_path_bar, expand=True, fill=True)
			self.pvr_path_bar.show_all()		
	
			pc_vbox = self.glade_xml.get_widget('pc_path_vbox')
			pc_vbox.pack_start(self.pc_path_bar, expand=True, fill=True)
			self.pc_path_bar.show_all()
	
			self.updatePathBar(self.pvr_model)
			self.updatePathBar(self.pc_model)
		
		# Timer to update screen info
		gobject.timeout_add(GuppyWindow.SCREEN_INFO_UPDATE_INTERVAL, self.updateScreenInfo)
		
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
	
		self.turbo = False
		
		self.last_file_transfer = None
		self.quit_after_transfer = False
		
	def initUIManager(self):
		"""Initialise the UIManager.
		
		Return: Dictionary with all actions for the toolbar.
		"""
		actions = {}
		
		self.uimanager = gtk.UIManager()
				
		actiongroup = gtk.ActionGroup('Actions')
		
		actiongroup.add_actions([('Quit', gtk.STOCK_QUIT, _('_Quit'), '<Ctrl>q', None, self.on_quit),
		                         ('File', None, _('_File')),
		                         ('View', None, _('_View')),
		                         ('Transfer', None, _('_Transfer')),
		                         ('Help', None, _('_Help')),
                                 ('About', gtk.STOCK_ABOUT , _('_About'), None, None, self.on_about)])

		actiongroup.add_actions([('GotoPCDir', None, _('Goto PC Location'), '<Ctrl>l', None, self.on_goto_pc_dir),
		                         ('GotoPVRDir', None, _('Goto PVR Location'), '<Ctrl>k', None, self.on_goto_pvr_dir),
		                         ('Reload', gtk.STOCK_REFRESH, _('Reload folders'), '<Ctrl>r', None, self.on_reload_dir)])
			                         
		actiongroup.add_toggle_actions([('QuitAfterTransfer', None, _('Quit After Transfer'), None, None, self.on_quit_after_transfer),
		                                ('ShowHidden', None, _('Show Hidden Files'), None, _('Show hidden files'), self.on_show_hidden_toggled),
		                                ('ShowFileTransfer', None, _('Show File Transfer'), None, _('Show File Transfer'), self.on_show_file_transfer_toggled)])

		turbo_act = gtk.ToggleAction('Turbo', _('Tur_bo'), _('Turbo Transfer'), None)
		turbo_act.connect('toggled', self.on_turbo_toggled)
		actiongroup.add_action_with_accel(turbo_act, '<Ctrl>t')
		actions['turbo'] = turbo_act
		
		# Create reference to ShowFileTransfer action so we can update the
		# toggle state accordingly when the transfer frame close button is
		# clicked.
		self.show_file_transfer_action = actiongroup.get_action('ShowFileTransfer')
		
		self.uimanager.insert_action_group(actiongroup, 0)
		
		# Create separate action group for upload so sensitivity can be set
		# according to selection in PC file tree
		self.upload_actiongrp = gtk.ActionGroup('UploadAction')                                 

		upload_act = gtk.Action('Upload',  _('_Upload'), _('Upload File'), gtk.STOCK_GO_BACK)
		upload_act.connect('activate', self.on_upload_btn_clicked)
		self.upload_actiongrp.add_action_with_accel(upload_act, '<Ctrl>u')
		actions['upload'] = upload_act

		self.upload_actiongrp.set_sensitive(False)
		self.uimanager.insert_action_group(self.upload_actiongrp, 1)

		# Create separate action group for download so sensitivity can be set
		# according to selection in PVR file tree
		self.download_actiongrp = gtk.ActionGroup('DownloadAction')                                 
		
		download_act = gtk.Action('Download', _('_Download'), _('Download File'), gtk.STOCK_GO_FORWARD)
		download_act.connect('activate', self.on_download_btn_clicked)
		self.download_actiongrp.add_action_with_accel(download_act, '<Ctrl>d')
		actions['download'] = download_act
		
		
		self.download_actiongrp.set_sensitive(False)
		self.uimanager.insert_action_group(self.download_actiongrp, 2)

		# Action group for File TreeView popup menu		
		self.file_actiongrp = gtk.ActionGroup('FileTreePopupAction')
		self.file_actiongrp.add_actions([('Delete', gtk.STOCK_DELETE, _('_Delete'), None, None, None),
		                                 ('Rename', None, _('_Rename'), None, None, None),
										 ('MakeDir', None, _('Create _Folder'), None, None, None),
										 ])
		self.uimanager.insert_action_group(self.file_actiongrp, 3)
		
		self.uimanager.add_ui_from_file(self.datadir + 'guppy-gtk.xml')

		self.file_popup = self.uimanager.get_widget('/FileTreePopup')
		self.file_popup_delete_btn = self.uimanager.get_widget('/FileTreePopup/Delete')
		self.file_popup_mkdir_btn = self.uimanager.get_widget('/FileTreePopup/MakeDir')
		self.file_popup_rename_btn = self.uimanager.get_widget('/FileTreePopup/Rename')
		
		self.file_popup.connect('selection-done', self.on_file_popup_done)
		
		return actions

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

			treeview.set_search_column(FileSystemModel.NAME_COL)
			treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
			
			treeview.connect('row-activated',
			                 self.on_treeview_row_activated,
			                 fs_model)
			handler_id = treeview.get_selection().connect('changed',
			                                              self.on_treeview_changed,
			                                              fs_model)
			# Store change handler id so we can block the 'changed' signal when
			# updating the tree view
			treeview.set_data('changed_handler_id', handler_id)
			
			# Connect callback to bring up popup menu
			treeview.connect('button-press-event',
			                 self.on_treeview_button_press,
			                 fs_model)

			treeview.connect('key-press-event',
			                 self.on_treeview_key_press,
			                 fs_model)

			# Text cell for file name			
			text_cell = gtk.CellRendererText()
			text_cell.set_property('ellipsize', pango.ELLIPSIZE_END)
			text_cell.set_property('ellipsize-set', True)
			# Pass in sorted_model because that is the model we will be getting
			# the tree path from.
			text_cell.connect('edited', self.on_name_cell_edited, liststore, fs_model)
			text_cell.connect('editing-canceled', self.on_name_cell_editing_cancelled)

			# Pixbuf cell for file icon
			pixb_cell = gtk.CellRendererPixbuf()
			
			col = gtk.TreeViewColumn(_('Name'))
			col.pack_start(pixb_cell, False)
			col.pack_start(text_cell, True)
			col.set_attributes(text_cell, text=FileSystemModel.NAME_COL)
			col.set_attributes(pixb_cell, pixbuf=FileSystemModel.ICON_COL)
			col.set_clickable(True)
			col.set_resizable(True)
			col.set_sort_indicator(True)
			col.set_expand(True)
			col.set_sort_column_id(FileSystemModel.NAME_COL)
			treeview.append_column(col)
			liststore.set_sort_func(FileSystemModel.NAME_COL, sort_func, FileSystemModel.NAME_COL)
						
			text_cell = gtk.CellRendererText()
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

	def deleteFiles(self, files, fs_model):
		"""Delete files from file system. Popup error dialog for errors.
	
		Return: True if all files deleted.
		"""
		retval = True
		for name in files:
			deleted = False
			while not deleted:
				try:
					fs_model.delete(name)
					deleted = True
				except OSError:
					SKIP, RETRY = range(2)
					msg = '<b>' + _('Error while deleting.') + '</b>\n\n' + _('Cannot delete')
					msg += ' "' + fs_model.getCWD() + '/' + name + '" '
					msg += _('because you do not have permissions to change it or its parent folder.')
					dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR)
					dialog.set_markup(msg)
					dialog.add_buttons( _('Skip'), SKIP, _('Retry'), RETRY)
					response = dialog.run()
					dialog.destroy()
		
					# Skip this file and go to next file
					if response == SKIP or response == gtk.RESPONSE_DELETE_EVENT:
						retval = False
						break
				
					# Try to delete again
					continue
				except PuppyBusyError:
					self.showNoFileOperationDialog()
					return
				except PuppyError, error:
					self.pvr_error_btn.show()
					self.pvr_error_window.addError(_('Failed to delete') + ' ' + name, error)
					break

		self.updateTreeViews(fs_model, True)
		self.updateFreeSpace(fs_model)
		
		return retval
	
	def hiddenFileFilter(self, model, iter, data=None):
		name = model.get_value(iter, FileSystemModel.NAME_COL)
		if self.show_hidden == False and (name == None or (name[0] == '.' and name[1] != '.')):
			return False
		
		return True
	
	def run(self):
		self.createFileTrees()
		
		if not self.puppy.exists():
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
			                           buttons=gtk.BUTTONS_OK)
			dialog.set_markup(_('''Guppy can not run because the program Puppy is not available. Please install Puppy.

You can download Puppy from <i>http://sourceforge.net/projects/puppy</i>'''))

			response = dialog.run()
			dialog.destroy()
			return

		self.updateScreenInfo()
		
		gtk.gdk.threads_enter()
		gtk.main()
		gtk.gdk.threads_leave()


	def on_about(self, widget, data=None):	
		dialog = gtk.AboutDialog()
		dialog.set_name(APP_NAME)
		dialog.set_authors([AUTHOR + ' ' + AUTHOR_EMAIL] + CONTRIBUTORS)
		dialog.set_copyright(COPYRIGHT)
		dialog.set_version(VERSION)
		dialog.set_license(LICENSE)
		dialog.set_website(WEBSITE)
		dialog.show()
	
	def on_column_clicked(self, col, data):
		order = col.get_sort_order()
		print order
		if order == gtk.SORT_ASCENDING:
			order = gtk.SORT_DESCENDING
		else:
			order = gtk.SORT_ASCENDING

		col.set_sort_order(order)
		data[0].set_sort_column_id(data[1], order)

	def on_delete_btn_clicked(self, widget, treeview, fs_model):
		selection = treeview.get_selection()
		model, rows = selection.get_selected_rows()
		
		files = []
		for path in rows:
			iter = model.get_iter(path)
			name = model.get_value(iter, FileSystemModel.NAME_COL)
			files.append(name)
			
		self.deleteFiles(files, fs_model)
			
	def on_download_btn_clicked(self, widget, data=None):
		self.transferFile('download')

	def on_file_popup_done(self, menushell):
		# Disconnect popup menuitem handlers as it is reconnected in
		# on_treeview_button_press().
		
		popup_widgets = [ self.file_popup_delete_btn, self.file_popup_mkdir_btn,
		                  self.file_popup_rename_btn ]
		
		for widget in popup_widgets:
			handler_id = widget.get_data('handler_id')
			if widget.handler_is_connected(handler_id):
				widget.disconnect(handler_id)

	def on_goto_pc_dir(self, widget, data=None):
		if self.pc_path_bar:
			self.pc_path_bar.hide()		
			self.pc_path_entry_box.show()
		self.pc_path_entry.grab_focus()

	def on_goto_pvr_dir(self, widget, data=None):		
		if self.pvr_path_bar:
			self.pvr_path_bar.hide()		
			self.pvr_path_entry_box.show()
		self.pvr_path_entry.grab_focus()

	def on_mkdir_btn_clicked(self, widget, treeview, fs_model):
		try:
			name = fs_model.mkdir()
		except OSError:
			msg = '<b>' + _('Error while creating folder.') + '</b>\n\n'
			msg += _('Can not create folder because you do not have permission to write in its parent folder.')
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE)
			dialog.set_markup(msg)
			response = dialog.run()
			dialog.destroy()

			return
		except PuppyBusyError:
			self.showNoFileOperationDialog()
			return
		except PuppyError, error:
			self.pvr_error_btn.show()
			self.pvr_error_window.addError(_('Failed to make a folder'), error)
			return
		
		# Update model to get new folder
		self.updateTreeViews(fs_model, True)
		
		# Get row for new folder		
		model = treeview.get_model()
		for row in model:
			if row[FileSystemModel.NAME_COL] == name:
				# Select row for new folder
				selection = treeview.get_selection()
				selection.unselect_all()
				selection.select_path(row.path)
				
				# Rename new folder
				self.on_rename_btn_clicked(widget, treeview, fs_model)
				break
		

	def on_name_cell_edited(self, cell, path, new_name, model, fs_model):
		# Set editable to False so users can't edit the cell by clicking on it.
		cell.set_property('editable', False)

		iter = model.get_iter(path)
		old_name = model.get_value(iter, FileSystemModel.NAME_COL)
		
		renamed = False
		while not renamed:
			try:
				fs_model.rename(old_name, new_name)
				renamed = True
			except OSError, error:
				print 'error = ', error

				# Handle Permission Denied error				
				if str(error).find('Errno 13') != -1:
					SKIP, RETRY = range(2)
					msg = '<b>' + _('Error while renaming.') + '</b>\n\n' + _('Cannot rename')
					msg += ' "' + fs_model.getCWD() + '/' + old_name + '" '
					msg += _('because you do not have permissions to change it or its parent folder.')
					dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR)
					dialog.set_markup(msg)
					dialog.add_buttons( _('Skip'), SKIP, _('Retry'), RETRY)
					response = dialog.run()
					dialog.destroy()
		
					# Skip this file and go to next file
					if response == SKIP or response == gtk.RESPONSE_DELETE_EVENT:
						retval = False
						break
				
					# Try to rename again
					continue
				elif str(error).find('Errno 17') != -1:
					CANCEL, REPLACE = range(2)
					msg = '<b>' + _('The item could not be renamed') + '.</b>\n\n'
					msg += _('The name') + ' "' + new_name + '" '
					msg += _('is already used in this folder.')
					dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR)
					dialog.set_markup(msg)
					dialog.add_buttons( _('Cancel'), CANCEL,_('Replace'), REPLACE)
					response = dialog.run()
					dialog.destroy()
		
					# Skip this file and go to next path in files
					if response == CANCEL or response == gtk.RESPONSE_DELETE_EVENT:
						break
		
					deleted = self.deleteFiles([new_name], fs_model)
					
					if not deleted:
						break
			except PuppyError, error:
				self.pvr_error_btn.show()
				self.pvr_error_window.addError(_('Failed to rename') + ' ' + old_name, error)
				break
		
		self.updateTreeViews(fs_model, True)

	def on_name_cell_editing_cancelled(self, cell, data=None):
		# Set editable to False so users can't edit the cell by clicking on it.
		cell.set_property('editable', False)

	def on_path_entry_activate(self, widget, fs_model):
		path = widget.get_text()

		dir_changed = fs_model.changeDir(path)
	
		if dir_changed == False:
			widget.set_text(fs_model.getCWD())
		
		if fs_model == self.pc_model:
			self.updateFreeSpace(self.pc_model)
			if self.no_path_bar_support == False:
				self.pc_path_entry_box.hide()
				if dir_changed:
					self.pc_path_bar.setPath(path)
				self.pc_path_bar.show()
		else:
			if self.no_path_bar_support == False:
				self.pvr_path_entry_box.hide()
				if dir_changed:
					self.pvr_path_bar.setPath(path)
				self.pvr_path_bar.show()
		
	def on_pvr_error_btn_clicked(self, widget, data=None):
		# TODO: Open error dialog
		self.pvr_error_window.show()
		widget.hide()
	
	def on_quit(self, widget, data=None):
		# Empty out transfer queue so the TransferThread can't get another
		# FileTransfer object after we cancel the current transfer.
		while True:
			try:
				file_transfer = self.transfer_queue.get_nowait()
			except Queue.Empty:
				break
				
			file_transfer.cancel()
			
		# Stop transfer if one is in progress
		self.puppy.cancelTransfer()

		# Add QUIT command to transfer queue.
		self.transfer_queue.put(GuppyWindow.QUIT_CMD)

		# We don't call gtk.main_quit() here because the TransferThread may try
		# to call some gtk functions. Instead if the TransferThread gets the
		# QUIT_CMD from the transfer queue it will call gtk.main_quit().

	def on_quit_after_transfer(self, widget, data=None):
		if self.quit_after_transfer:
			self.quit_after_transfer = False
			if self.last_file_transfer != None and self.last_file_transfer.isAlive():
				self.last_file_transfer.setQuitAfterTransfer(False)
		else:
			self.quit_after_transfer = True
			if self.last_file_transfer != None and self.last_file_transfer.isAlive():
				self.last_file_transfer.setQuitAfterTransfer(True)

	def on_reload_dir(self, widget, data=None):
		self.updateTreeViews()
		
	def on_rename_btn_clicked(self, widget, treeview, fs_model):
		# Fail rename on PVR if a transfer is in progress
		if isinstance(fs_model, PVRFileSystemModel) and self.puppy.isActive():
			self.showNoFileOperationDialog()
			return
		
		selection = treeview.get_selection()
		model, files = selection.get_selected_rows()
		
		path = files[0]
		iter = model.get_iter(path)
		col = treeview.get_column(0)
		cells = col.get_cell_renderers()
		cells[1].set_property('editable', True)
		treeview.set_cursor(path, col, start_editing=True)
					
	def on_show_file_transfer_toggled(self, widget, data=None):
		transfer_frame = self.glade_xml.get_widget('transfer_frame')
		if widget.get_active():
			self.show_transfer_frame()
		else:
			transfer_frame.hide()
					
	def on_show_hidden_toggled(self, widget, data=None):
		self.show_hidden = not self.show_hidden
		self.pc_liststore.get_model().refilter()
		self.pvr_liststore.get_model().refilter()
	
	def on_treeview_button_press(self, treeview, event, fs_model):
		if event.button == 3:
			time = event.time

			selection = treeview.get_selection()
			model, files = selection.get_selected_rows()
			if len(files) == 1:
				self.file_popup_rename_btn.set_sensitive(True)
			else:
				self.file_popup_rename_btn.set_sensitive(False)
				
			if len(files) >= 1:
				self.file_popup_delete_btn.set_sensitive(True)
			else:
				self.file_popup_delete_btn.set_sensitive(False)

			btns = [ (self.file_popup_delete_btn, self.on_delete_btn_clicked),
			         (self.file_popup_rename_btn, self.on_rename_btn_clicked),
			         (self.file_popup_mkdir_btn, self.on_mkdir_btn_clicked) ]

			# Connect signal handler for each popup menuitem with the treeview
			# and fs_model where the popup menu appeared.
			for btn, callback in btns:
				handler_id = btn.connect('activate',
				                         callback,
				                         treeview,
				                         fs_model)
				btn.set_data('handler_id', handler_id)
				
			self.file_popup.popup( None, None, None, event.button, time)
			
			# Return True so row selection doesn't get changed.
			return True
		
	def on_treeview_changed(self, widget, fs_model):
		""" Update status bar with selection size and button sensitivity.
		
		    Update the total size of all files selected and the sensitivity of
		    download/upload button based on row selection.
		    
		"""
		model, files = widget.get_selected_rows()
		
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

	def on_treeview_key_press(self, treeview, event, fs_model):
		
		# <F2>: Rename selected file.
		if event.keyval == 65471:
			selection = treeview.get_selection()
			model, files = selection.get_selected_rows()
			if len(files) == 1:
				self.on_rename_btn_clicked(None, treeview, fs_model)
	
	def on_treeview_row_activated(self, widget, path, col, fs_model):
		model = widget.get_model()
		iter = model.get_iter(path)
		name = model.get_value(iter, FileSystemModel.NAME_COL)
		type = model.get_value(iter, FileSystemModel.TYPE_COL)
		
		if type == 'd':
			fs_model.changeDir(name)
			path = fs_model.getCWD()
			if fs_model == self.pc_model:
				if self.no_path_bar_support == False:
					self.pc_path_entry_box.hide()
					self.pc_path_bar.setPath(path)
					self.pc_path_bar.show()
				self.pc_path_entry.set_text(path)
				self.updateFreeSpace(self.pc_model)
			else:
				if self.no_path_bar_support == False:
					self.pvr_path_entry_box.hide()
					self.pvr_path_bar.setPath(path)
					self.pvr_path_bar.show()
				self.pvr_path_entry.set_text(path)
			
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

	def on_transfer_remove_btn_clicked(self, widget, file_transfer):
		file_transfer.cancel()
		
		progress_box = file_transfer.xml.get_widget('progress_box')
		progress_box.destroy()

	def on_transfer_stop_btn_clicked(self, widget, file_transfer):
		# Don't quit if user explicitly stopped the transfer the last transfer
		if file_transfer == self.last_file_transfer:
			self.last_file_transfer.setQuitAfterTransfer(False)
		self.puppy.cancelTransfer()

	def on_turbo_toggled(self, widget, data=None):
		self.turbo = widget.get_active()

	def on_upload_btn_clicked(self, widget, data=None):
		self.transferFile('upload')

	def on_window_delete_event(self, widget, event, data=None):
		self.on_quit(widget, data)
		# Return True to stop event from propagating to default handler
		# which destroys the window.
		return True

	def reallyQuit(self):
		gtk.main_quit()

	def showNoFileOperationDialog(self):
		dialog = gtk.MessageDialog(message_format=_('It is not possible to delete, rename, or create folders on the PVR during a file transfer.'),
		                           type=gtk.MESSAGE_ERROR,
		                           buttons=gtk.BUTTONS_CLOSE)
		dialog.run()
		dialog.destroy()
		
	def show_transfer_frame(self):
		# Set position of pane separator
		# Give progress frame height of 180 pixels. This should be enough room
		# to show two file transfers.
		vpane = self.glade_xml.get_widget('vpane')
		vpane.set_position(vpane.get_allocation().height - 188)
		
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
			try:
				free_space = self.pvr_model.freeSpace()
			except PuppyError, error:
				self.pvr_error_btn.show()
				self.pvr_error_window.addError(_('Failed to get free disk space'), error)
				
				# Assume there is enough space on the PVR
				free_space = selection_size
				pass

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
		
		# Show File Transfer pane
		self.show_file_transfer_action.set_active(True)

		existing_files = []
		for path in files:
			iter = model.get_iter(path)
			file = model.get_value(iter, FileSystemModel.NAME_COL)
			date = model.get_value(iter, FileSystemModel.DATE_COL)

			if direction == 'download':
				src_dir = self.pvr_model.getCWD()
				dst_dir = self.pc_model.getCWD()
				src_file = src_dir + '\\' + file
				dst_file = dst_dir + '/' + file
				file_exists = os.access(dst_file, os.F_OK)
			else:
				src_dir = self.pc_model.getCWD()
				dst_dir = self.pvr_model.getCWD()
				src_file = src_dir + '/' + file
				dst_file = dst_dir + '\\' + file
				file_exists = self.pvr_model.find(file)

			xml = gtk.glade.XML(self.glade_file, 'progress_box')
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
	
			file_transfer = FileTransfer(direction, src_file, dst_file,
			                             date, xml)

			# Connect transfer instance remove button signal handler
			remove_btn = xml.get_widget('transfer_remove_button')
			remove_btn.connect('clicked', self.on_transfer_remove_btn_clicked, file_transfer)
			stop_btn = xml.get_widget('transfer_stop_button')
			stop_btn.connect('clicked', self.on_transfer_stop_btn_clicked, file_transfer)

			if file_exists:
				existing_files.append(file_transfer)
			else:
				queue_box.pack_start(progress_box, expand=False)
				self.transfer_queue.put(file_transfer, True, None)

		old_last_file_transfer = self.last_file_transfer
		self.last_file_transfer = file_transfer
		
		# Confirm with user that they wish to overwrite existing files
		replace_all = False
		for file in existing_files:
			if replace_all == False:
				SKIP, REPLACE, REPLACE_ALL = range(3)
				msg = _('The file') + ' "' + file.dst + '" ' + _('already exists. Would you like to replace it?')
				msg2 = _('If you replace an existing file, its contents will be overwritten.')
				dialog = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
				                           message_format=msg)
				                           
				if len(existing_files) > 1:
					dialog.add_button(_('Replace All'), REPLACE_ALL)
				dialog.add_buttons( _('Skip'), SKIP, _('Replace'), REPLACE)
				response = dialog.run()
				dialog.destroy()
	
				if response == SKIP or response == gtk.RESPONSE_DELETE_EVENT:
					continue
					
				if response == REPLACE_ALL:
					replace_all = True

			progress_box = file.xml.get_widget('progress_box')
			queue_box.pack_start(progress_box, expand=False)
			self.transfer_queue.put(file, True, None)
			self.last_file_transfer = file

		if self.quit_after_transfer:
			if old_last_file_transfer:
				old_last_file_transfer.setQuitAfterTransfer(False)
			
			self.last_file_transfer.setQuitAfterTransfer(True)
			
	def updateFreeSpace(self, fs_model=None):			
		'''Update label showing free space available on each file system.
	
		fs_model  Model to update free space. Default is None which updates both
		          file system.
		'''
		try:
			if fs_model == self.pvr_model or fs_model == None:
				self.pvr_free_space_label.set_text(_('Free Space') + ': ' + self.pvr_model.freeSpace())
		except PuppyNoPVRError:
			raise
		except PuppyError, error:
			self.pvr_error_btn.show()
			self.pvr_error_window.addError(_('Failed to get free disk space'), error)
			pass
			
		if fs_model == self.pc_model or fs_model == None:
			self.pc_free_space_label.set_text(_('Free Space') + ': ' + self.pc_model.freeSpace())

	def updatePathBar(self, fs_model):
		'''Update the buttons of the path bar for each file system.

		fs_model  Model to update path bar. Default is None which updates both
		          file system.
		'''
		if self.no_path_bar_support:
			return
			
		if fs_model == self.pvr_model:
			self.pvr_path_bar.setPath(fs_model.getCWD())
		else:
			self.pc_path_bar.setPath(fs_model.getCWD())
	
	def updateScreenInfo(self):
		try:
			# Update amount of free space available
			self.updateFreeSpace()
			
			# Update treeviews.
			self.updateTreeViews()
		except PuppyNoPVRError, error:
			self.pvr_error_btn.show()
			self.pvr_error_window.addError(_('PVR not connected'), error)
			pass
			
		return True
	

	def updateTreeViews(self, fs_model=None, cur_dir_only=False):
		# Update FileSystemModel view
		if fs_model == self.pc_model:
			models = [ (self.pc_model, self.pc_treeview) ]
		elif fs_model == self.pvr_model:
			models = [ (self.pvr_model, self.pvr_treeview) ]
		else:
			models = [ (self.pc_model, self.pc_treeview), (self.pvr_model, self.pvr_treeview) ]
		
		for model, treeview in models:
			handler_id = treeview.get_data('changed_handler_id')
			selection = treeview.get_selection()
			
			# Store currently selected rows because they will be wiped when
			# the data model is updated.
			selected_rows = selection.get_selected_rows()
			
			selection.handler_block(handler_id)
			# Update PVR file system cache
			if isinstance(model, PVRFileSystemModel):
				try:
					if cur_dir_only:
						model.updateDirectory(model.getCWD())
					else:
						model.updateCache()
				except PuppyNoPVRError:
					raise
				except PuppyError, error:
					self.pvr_error_btn.show()
					self.pvr_error_window.addError(_('Failed to get list of files'), error)
					pass

			model.changeDir()
			selection.handler_unblock(handler_id)
			
			# Reselect rows
			for path in selected_rows[1]:
				selection.select_path(path)


class PVRErrorWindow:
	ICON_COL, ICON_SIZE_COL, MSG_COL, OUTPUT_COL = range(4)
	LIST_TYPES = []
	LIST_TYPES.insert(ICON_COL, gobject.TYPE_STRING)
	LIST_TYPES.insert(ICON_SIZE_COL, gobject.TYPE_UINT)
	LIST_TYPES.insert(MSG_COL, gobject.TYPE_STRING)
	LIST_TYPES.insert(OUTPUT_COL, gobject.TYPE_STRING)

	def __init__(self, glade_file):
		glade_xml = gtk.glade.XML(glade_file, 'pvr_error_window')
		# Connect callback functions in glade file to functions
		glade_xml.signal_autoconnect(self)

		self.glade_file = glade_file		
		self.error_window = glade_xml.get_widget('pvr_error_window')
		self.pvr_error_output = glade_xml.get_widget('pvr_error_output')
		self.pvr_error_box = glade_xml.get_widget('pvr_error_box')

		self.liststore = gtk.ListStore(PVRErrorWindow.LIST_TYPES[PVRErrorWindow.ICON_COL],
		                               PVRErrorWindow.LIST_TYPES[PVRErrorWindow.ICON_SIZE_COL],
		                               PVRErrorWindow.LIST_TYPES[PVRErrorWindow.MSG_COL],
		                               PVRErrorWindow.LIST_TYPES[PVRErrorWindow.OUTPUT_COL])

		self.pvr_error_treeview = glade_xml.get_widget('pvr_error_treeview')

		self.pvr_error_treeview.set_model(self.liststore)
		handler_id = self.pvr_error_treeview.get_selection().connect('changed', self.on_pvr_error_treeview_changed)
		
		text_cell = gtk.CellRendererText()
		pixb_cell = gtk.CellRendererPixbuf()
		
		col = gtk.TreeViewColumn()
		col.pack_start(pixb_cell, False)
		col.pack_start(text_cell, True)
		col.set_attributes(text_cell, markup=PVRErrorWindow.MSG_COL)
		col.set_attributes(pixb_cell, stock_id=PVRErrorWindow.ICON_COL, stock_size=PVRErrorWindow.ICON_SIZE_COL)
		self.pvr_error_treeview.append_column(col)
		
	def addError(self, msg, error_output):
		error_msg = _('ERROR') + ': ' + time.strftime('%a %b %d, %I:%M %p', time.localtime()) +'\n'
		error_msg += '<b>' + msg + '</b>'
		
		self.liststore.append([gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_DIALOG, error_msg, error_output])

	def on_expander_activate(self, widget):
		if widget.get_property('expanded'):
			box_expand = False
		else:
			box_expand = True
			
		self.pvr_error_box.set_child_packing(widget, box_expand, True, 0,
		                                     gtk.PACK_START)
		
	def on_pvr_error_treeview_changed(self, widget):
		model, iter = widget.get_selected()
		if iter == None:
			return
		
		textbuf = gtk.TextBuffer()
		textbuf.set_text(model.get_value(iter, PVRErrorWindow.OUTPUT_COL))
		
		self.pvr_error_output.set_buffer(textbuf)

	def on_pvr_error_window_clear(self, widget, data=None):
		self.liststore.clear()
		textbuf = self.pvr_error_output.get_buffer()
		textbuf.set_text('')

	def on_pvr_error_window_close(self, widget, event=None, data=None):
		self.error_window.hide()
		return True
		
	def show(self):
		self.error_window.show()

class FileTransfer:
	def __init__(self, direction, src, dst, file_date, xml):
		self.direction = direction
		self.src = src
		self.dst = dst
		self.xml = xml
		self.file_date = file_date
		
		self.alive = True
		self.quit_after_transfer = False
	
	def isAlive(self):
		return self.alive
		
	def cancel(self):
		self.alive = False
	
	def complete(self):
		self.alive = False
		
	def getQuitAfterTransfer(self):
		return self.quit_after_transfer
	
	def setQuitAfterTransfer(self, value):
		self.quit_after_transfer = value
		
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

			# Check if guppy is quiting
			if file_transfer == GuppyWindow.QUIT_CMD:
				gtk.gdk.threads_enter()
				self.guppy.reallyQuit()
				gtk.gdk.threads_leave()
				return
				
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
			stop_btn.set_size_request(allocation.width, allocation.height)
			gtk.gdk.threads_leave()

			progress_bar = xml.get_widget('transfer_progressbar')
			
			# Enable turbo mode if required
			if self.guppy.turbo == True:
				self.guppy.puppy.setTurbo(True)
				
			try:
				if direction == 'download':
					self.guppy.puppy.getFile(src_file, dst_file)
				else:
					self.guppy.puppy.putFile(src_file, dst_file)
			except PuppyError:
				pass

			transfer_successful = True
			transfer_attempt = 1
			percent = True			
			while percent != None:
				try:
					percent, speed, transfer_time = self.guppy.puppy.getProgress()
				except PuppyError, error:
					# Quit trying to transfer file after a certain number of attempts
					if transfer_attempt > TransferThread.NUM_OF_TRANSFER_ATTEMPTS:
						transfer_successful = False
						transfer_error = error
						break
					
					transfer_attempt += 1

					# Try to reset PVR before attempt transfer again
					reset_successful = False
					attempts = 0
					while not reset_successful and attempts < TransferThread.NUM_OF_RESET_ATTEMPTS:
						reset_successful = self.guppy.puppy.reset()
						attempts += 1

					try:
						if direction == 'download':
							self.guppy.puppy.getFile(src_file, dst_file)
						else:
							self.guppy.puppy.putFile(src_file, dst_file)
					except PuppyError:
						pass

					continue

				# Transfer may have completed
				if percent is None:
					break
					
				gtk.gdk.threads_enter()
				progress_bar.set_fraction(float(percent)/100)
				progress_bar.set_text('(' + transfer_time['remaining'] + ' ' + _('Remaining') + ')')

				while gtk.events_pending():
					gtk.main_iteration()
				gtk.gdk.threads_leave()

			# Disable turbo mode. The PVR remote control can not be used if
			# turbo mode is left on.
			if self.guppy.turbo == True:
				self.guppy.puppy.setTurbo(False)

			# Set modification time of downloaded file to the same time as the
			# as on the PVR.
			if transfer_successful and direction == 'download':
				# Parse date string
				time_struct = time.strptime(file_transfer.file_date, '%a %b %d %Y')
				
				# Convert to seconds since the epoch
				time_secs = time.mktime(time_struct)
				
				# Set modification time
				os.utime(dst_file, (int(time.time()), time_secs))
			
			gtk.gdk.threads_enter()
			if transfer_successful:
				progress_bar.set_fraction(1)

				progress_bar.set_text(_('Finished'))
			else:
				progress_bar.set_text(_('Transfer Failed'))
				self.guppy.pvr_error_btn.show()

				if direction == 'download':
					msg = _('Failed to download:') + '\n' + src_file
				else:
					msg = _('Failed to upload: ') + '\n' + src_file

				self.guppy.pvr_error_window.addError(msg, transfer_error)

			gtk.gdk.threads_leave()
				

			# Desensitise all widgets			
			for widget in ['progress_hbox1', 'progress_hbox2']:
				widget = xml.get_widget(widget)
				gtk.gdk.threads_enter()
				widget.set_sensitive(False)
				gtk.gdk.threads_leave()

			# Swap Stop button for Remove button
			gtk.gdk.threads_enter()
			stop_btn.hide()
			remove_btn.show()
			gtk.gdk.threads_leave()

			file_transfer.complete()
			
			# Update file treeviews
			gtk.gdk.threads_enter()
			self.guppy.updateTreeViews()
			gtk.gdk.threads_leave()
			
			# Put on queue for completed transfers
			self.complete_queue.put(file_transfer)
			
			if file_transfer.getQuitAfterTransfer():
				gtk.gdk.threads_enter()
				self.guppy.reallyQuit()
				gtk.gdk.threads_leave()
				return

class PathBar(gtk.Container):
	__gtype_name__ = 'PathBar'
	
	def __init__(self, guppy, fs):
		gtk.Container.__init__(self)
		self.spacing = 3

		self.set_flags(gtk.NO_WINDOW)		
		
		self.guppy = guppy
		self.fs = fs
		self.btn_list = []
		self.path = None
		self.active_btn = None
		
		gtk.widget_push_composite_child()
		self.down_btn = gobject.new(gtk.Button, visible=True)
		arrow = gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_OUT)
		self.down_btn.add(arrow)
		self.down_btn.show_all()
		self.down_btn.connect('clicked', self.on_down_btn_clicked)
		
		self.up_btn = gobject.new(gtk.Button, visible=True)
		arrow = gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_OUT)
		self.up_btn.add(arrow)
		self.up_btn.show_all()
		self.up_btn.connect('clicked', self.on_up_btn_clicked)
		gtk.widget_pop_composite_child()

		self.down_btn.set_parent(self)
		self.up_btn.set_parent(self)
		
		# Add root dir button
		self.root_btn = gtk.ToggleButton()
		label = gtk.Label('/')
		self.root_btn.set_data('label', label)
				
		icon_theme = gtk.icon_theme_get_default()
		try:
			settings = gtk.settings_get_for_screen(self.get_screen())
			icon_size = gtk.icon_size_lookup_for_settings(settings, gtk.ICON_SIZE_MENU)
			if icon_size:
				icon_size = max(icon_size[0], icon_size[1])
			else:
				icon_size = 16

			pixbuf = icon_theme.load_icon('gnome-dev-harddisk', icon_size, gtk.ICON_LOOKUP_USE_BUILTIN)
			if pixbuf == None:
				pixbuf = self.render_icon(gtk.STOCK_HARDDISK, gtk.ICON_SIZE_MENU, 'root dir')
				
			image = gtk.Image()
			image.set_from_pixbuf(pixbuf)
			self.root_btn.add(image)
				
		except gobject.GError, exc:
			print "ERROR: Can't load icon: ", exc	
			self.root_btn.add(label)

		btn_handler_id = self.root_btn.connect('clicked', self.on_path_btn_clicked, '/')
		self.root_btn.set_data('handler_id', btn_handler_id)
		
		self.add(self.root_btn)
		self.btn_list.append(self.root_btn)

		self.first_scrolled_btn = None
		
	def do_add(self, widget):
		widget.set_parent(self)
	
	def do_forall(self, internal, callback, data):
		if internal:
			callback(self.down_btn, data)
			callback(self.up_btn, data)
		for btn in self.btn_list:
			callback(btn, data)
	
	def do_remove(self, widget):
		was_visible = widget.get_property('visible')
		widget.unparent()
		if was_visible:
			self.queue_resize()
		
	def do_size_request(self, requisition):
		#print 'do_size_request()'
		req_width = 0
		req_height = 0
		widgets = [ self.down_btn, self.up_btn ] + self.btn_list

		for widget in widgets:
			widget_req = gtk.gdk.Rectangle(0, 0, *widget.size_request())
			req_width += widget_req.width
			req_height = max(req_height, widget_req.height)

		requisition.width = req_width + (self.border_width * 2)
		requisition.height = req_height + (self.border_width * 2)
		
		self.requisition = requisition
		
		
	def do_size_allocate(self, allocation):
		#print '\n\n\ndo_size_allocate(): allocation.width = %d allocation.height = %d' % (allocation.width, allocation.height)

		self.allocation = allocation
		
		if len(self.btn_list) == 0:
			return
			
		# Check to see if slider button required
		total_btn_width = 0
		for btn in self.btn_list:
			width, height = btn.get_child_requisition()
			total_btn_width += width + self.spacing
		
		width, height = self.down_btn.get_child_requisition()
		down_offset = width + self.spacing
		
		width, height = self.up_btn.get_child_requisition()
		up_offset = width
		
		alloc_width = allocation.width - (self.border_width * 2)
		alloc_height = allocation.height - (self.border_width * 2)
		alloc_x = allocation.x + self.border_width
		alloc_y = allocation.y + self.border_width
		if total_btn_width <= alloc_width:
			need_slider = False
			start_idx = 0
			cur_x = alloc_x
		else:
			need_slider = True
			start_idx = None
			cur_x = alloc_x + down_offset
			alloc_width -= down_offset + up_offset

			if self.first_scrolled_btn != None:
				start_idx = self.first_scrolled_btn
			else:	
				# self.first_scrolled_btn is None which means we are
				# allocating space for a new path. This means that the last dir
				# will be the one required to be visible.
				start_idx = len(self.btn_list) - 1
				
			#print 'alloc_width = ', alloc_width, ' start_idx=', start_idx

			cur_width = 0
			filled_space = False

			# See if we can fill the space with btns to the right of start_idx
			for btn in self.btn_list[start_idx:]:
				width, height = btn.get_child_requisition()
				cur_width += width + self.spacing
				
				#print 'do_size_allocate() cur_width = ', cur_width, 'idx=', self.btn_list.index(btn), ' label = ', btn.get_data('label').get_text(), ' width = ', width
				if cur_width > alloc_width:
					filled_space = True
					break

			# If we didn't fill all the available space with buttons from the 
			# right of start_idx fill in with buttons to the left of start_idx.
			if filled_space == False:
				for i in xrange(start_idx-1, -1, -1):
					width, height = self.btn_list[i].get_child_requisition()
					cur_width += width + self.spacing
					
					#print 'do_size_allocate() cur_width = ', cur_width, ' i=', i, ' label = ', self.btn_list[i].get_data('label').get_text(), ' width = ', width
					if cur_width > alloc_width:
						break
						
				start_idx = i + 1	
				
		# Allocate space for all buttons from start_idx until we run out of
		# space.		
		cur_width = 0
		# Intialise end_idx to start_idx - 1 incase there is only one button
		end_idx = start_idx-1
		for btn in self.btn_list[start_idx:]:
			width, height = btn.get_child_requisition()

			rect  = gtk.gdk.Rectangle(x=cur_x, y=alloc_y, width=width, height=alloc_height)

			cur_x += width + self.spacing
			cur_width += width + self.spacing

			if cur_width > alloc_width:
				break

			end_idx += 1
			btn.size_allocate(rect)
			btn.show()

		#print 'do_size_allocate(): first_scrolled_btn = ', self.first_scrolled_btn, ' need_slider = ', need_slider, ' start_idx = ', start_idx, ' end_idx = ', end_idx
		
		# Hide all buttons before start_idx
		for i in xrange(start_idx-1, -1, -1):
			self.btn_list[i].hide()
			
		# Hide all buttons after end_idx
		for btn in self.btn_list[end_idx+1:]:
			btn.hide()
			
		if need_slider:
			width, height = self.down_btn.get_child_requisition()
			rect  = gtk.gdk.Rectangle(x=alloc_x, y=alloc_y, width=width, height=alloc_height)
			self.down_btn.size_allocate(rect)
			# If first button is already visible then we can't go down anymore
			if self.btn_list[0].get_property('visible'):
				self.down_btn.set_sensitive(False)
			else:
				self.down_btn.set_sensitive(True)
				
			self.down_btn.show()

			width, height = self.up_btn.get_child_requisition()
			rect  = gtk.gdk.Rectangle(y=alloc_y, width=width, height=alloc_height)
			rect.x = allocation.x + allocation.width - width - self.border_width
			self.up_btn.size_allocate(rect)
			# If last button is already visible then we can't go up anymore
			if self.btn_list[-1].get_property('visible'):
				self.up_btn.set_sensitive(False)
			else:
				self.up_btn.set_sensitive(True)
			self.up_btn.show()
			
		else:
			self.down_btn.hide()
			self.up_btn.hide()
			
	def on_path_btn_clicked(self, widget, path):
		self.updatePathBtns(path)

		if self.fs == 'pvr':
			path = path.replace('/', '\\')
			self.guppy.pvr_model.changeDir(path)
			self.guppy.pvr_path_entry.set_text(path)
		else:
			self.guppy.pc_model.changeDir(path)
			self.guppy.pc_path_entry.set_text(path)

	def on_down_btn_clicked(self, btn):
		self.queue_resize()

		for i in xrange(len(self.btn_list)):
			# The button before the currently left most visible button should
			# be shown.
			if self.btn_list[i].get_property('visible'):
				self.first_scrolled_btn = i - 1
				break
			
		# This happens when there are no more buttons to scroll to the left
		if self.first_scrolled_btn == -1:
			self.first_scrolled_btn = 0
			
	def on_up_btn_clicked(self, btn):
		self.queue_resize()
		
		# Start search for first non-visible button on the right.
		for i in xrange(len(self.btn_list)-1, -1, -1):
			if self.btn_list[i].get_property('visible'):
				start_idx = i + 1
				break
		
		#print '\n\n\non_up_btn_clicked(): start_idx = ', start_idx, ' label = ', self.btn_list[start_idx].get_data('label').get_text()
		pathbar = self.get_allocation()
		alloc_width = pathbar.width
		
		# Subtract space for down slider button
		width, height = self.down_btn.get_child_requisition()
		alloc_width -= width + self.spacing
		
		# Subtract space for up slider button
		width, height = self.up_btn.get_child_requisition()
		alloc_width -= width
		
		# Find all the buttons to the left of start_idx which will fit.
		cur_width = 0		
		for i in xrange(start_idx, -1, -1):
			btn_alloc = self.btn_list[i].get_allocation()
			cur_width += btn_alloc.width + self.spacing
			
			#print 'on_up_btn_clicked(): cur_width = ', cur_width, ' i = ', i, ' label = ', self.btn_list[i].get_data('label').get_text(), ' width = ', btn_alloc.width
			if cur_width >= alloc_width:
				break
		self.first_scrolled_btn = i + 1
		
	def setPath(self, path):
		path = path.replace('\\', '/')
		path = os.path.normpath(path)
		# os.path.normpath() doesn't normalise '//' to '/'
		if path == '//':
			path = '/'
		
		# Check if we are changing to a dir on the same path
		if self.updatePathBtns(path):
			return
		
		self.path = path

		bar_bound = self.get_allocation()
		cur_width = 0
		
		# Remove existing buttons
		for btn in self.btn_list[1:]:
			self.remove(btn)
			self.btn_list.remove(btn)
			btn.destroy()
			
		# New path so reset the left most button state
		self.first_scrolled_btn = None
		
		# Reset root button
		if self.active_btn == self.root_btn:
			handler_id = self.active_btn.get_data('handler_id')
			self.active_btn.handler_block(handler_id)
			self.active_btn.set_active(False)
	
			label = self.active_btn.get_data('label')
			label.set_text(label.get_text())
			self.active_btn.handler_unblock(handler_id)
						
		dirs = path.split('/')

		path = ''
		btn = None
		for dir in dirs:
			if len(dir) > 0:
				path += '/' + dir
				
				label = gtk.Label(dir)
				btn = gtk.ToggleButton()
				btn.add(label)
				btn.set_data('label', label)
				
				self.add(btn)
				self.btn_list.append(btn)
				
				btn_handler_id = btn.connect('clicked', self.on_path_btn_clicked, path)
				btn.set_data('handler_id', btn_handler_id)
				
		if btn == None:
			btn = self.root_btn
			btn_handler_id = self.root_btn.get_data('handler_id')
			
		# Activate last button
		btn.handler_block(btn_handler_id)
		btn.set_active(True)
		label = btn.get_data('label')
		label.set_markup('<b>' + label.get_text() + '</b>')
		btn.handler_unblock(btn_handler_id)
		self.active_btn = btn

		self.show_all()		
	
	def updatePathBtns(self, path):
		"""Update toggle state of path bar buttons if we change to a dir on the current path.
		"""
		if self.path == None or not self.path.startswith(path):
			return False

		if path != '/':
			last_dir = path.split('/')[-1]
		else:
			last_dir = '/'

		for btn in self.btn_list:
			label = btn.get_data('label')
			if label.get_text() == last_dir:
				# Block clicked signal and untoggle old active btn
				handler_id = self.active_btn.get_data('handler_id')
				self.active_btn.handler_block(handler_id)
				self.active_btn.set_active(False)

				label = self.active_btn.get_data('label')
				label.set_text(label.get_text())
				self.active_btn.handler_unblock(handler_id)
				
				handler_id = btn.get_data('handler_id')
				btn.handler_block(handler_id)
				btn.set_active(True)

				label = btn.get_data('label')
				label.set_markup('<b>' + label.get_text() + '</b>')
				btn.handler_unblock(handler_id)

				self.active_btn = btn
				if btn.get_property('visible') == False:
					self.first_scrolled_btn = self.btn_list.index(btn)
				return True
				
		return False

# Need to register PathBar widget in order to override gtk.HBox methods
gobject.type_register(PathBar)

if __name__ == "__main__":
	locale.setlocale(locale.LC_ALL, '')
	gettext.bindtextdomain(APP_NAME, 'i18n')
	gettext.textdomain(APP_NAME)
	gettext.install(APP_NAME, 'i18n', unicode=1)
	
	guppy = GuppyWindow()
	guppy.run()
