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
from PVRErrorWindow import *
from PathBar import *
from FileTransfer import *
from TransferThread import *

class GuppyWindow:
	SCREEN_INFO_UPDATE_INTERVAL = 10 * 60 * 1000 # 10 mins (unit in milliseconds)
	
	# Quit command to put on transfer queue
	QUIT_CMD = 'Quit'
	
	def __init__(self, datadir='', dirname=None):	
		# The PathBar widget only works with PyGtk 2.8 and greater
		major, minor, micro = gtk.pygtk_version
		if major <= 2 and minor < 8:
			self.no_path_bar_support = True
		else:
			self.no_path_bar_support = False

		if os.path.exists(datadir + '/pixmaps/'):
			pixmap_dir = datadir + '/pixmaps/'
		else:
			pixmap_dir = datadir + '/../pixmaps/'
			
		self.dirname = dirname
		
		# Exclude caching contents of MP3 by default
		self.cache_exclusions = [ '\\MP3' ]
		
		# Find out proper way to find glade files
		self.glade_file = datadir + '/' + 'guppy.glade'

		self.pvr_error_window = PVRErrorWindow(self.glade_file, self.dirname)

		# Initialise Gtk thread support
		gtk.gdk.threads_init()

		actions = self.initUIManager(datadir)

		# This must be done before loading the glade file.
		gtk.glade.set_custom_handler(self.customWidgetHandler)
		
		# Load glade file
		self.glade_xml = gtk.glade.XML(self.glade_file,
		                               None,
		                               self.dirname)
		
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

		self.pc_model = PCFileSystemModel(pixmap_dir,
		                                  cwd=getConfValue('PC_CWD'),
		                                  show_parent_dir=show_parent_dir)
		self.pvr_model = PVRFileSystemModel(pixmap_dir,
		                                    cwd=getConfValue('PVR_CWD'),
		                                    show_parent_dir=show_parent_dir)
		
		self.pc_path = {}
		self.pc_path['entry_box'] = self.glade_xml.get_widget('pc_path_entry_box')
		
		self.pvr_path = {}
		self.pvr_path['entry_box'] = self.glade_xml.get_widget('pvr_path_entry_box')
		
		self.pc_path['bar'] = None
		self.pvr_path['bar'] = None
		if self.no_path_bar_support:
			self.pc_path['entry_box'].show()
			self.pvr_path['entry_box'].show()
		else:
			self.pvr_path['bar'] = PathBar(self, 'pvr')
			self.pvr_path['bar'].set_border_width(3)
			
			self.pc_path['bar'] = PathBar(self, 'pc')
			self.pc_path['bar'].set_border_width(3)
			
			pvr_vbox = self.glade_xml.get_widget('pvr_path_vbox')
			pvr_vbox.pack_start(self.pvr_path['bar'], expand=True, fill=True)
			self.pvr_path['bar'].show_all()		
	
			pc_vbox = self.glade_xml.get_widget('pc_path_vbox')
			pc_vbox.pack_start(self.pc_path['bar'], expand=True, fill=True)
			self.pc_path['bar'].show_all()
	
			self.updatePathBar(self.pvr_model)
			self.updatePathBar(self.pc_model)

		actions['goto_pc_dir'].connect('activate', self.on_goto_dir, self.pc_path, self.pc_model)
		actions['goto_pvr_dir'].connect('activate', self.on_goto_dir, self.pvr_path, self.pvr_model)
		
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
		self.turbo_warn = True
		
		self.last_file_transfer = None
		self.quit_after_transfer = False

	def initUIManager(self, datadir):
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
		                         ('About', gtk.STOCK_ABOUT , _('_About'), None, None, self.on_about),
		                         ('Reload', gtk.STOCK_REFRESH, _('Reload folders'), '<Ctrl>r', None, self.on_reload_dir)])

		action = gtk.Action('GotoPVRDir', _('Go to PVR Location'), _('Go to PVR Location'), None)
		actiongroup.add_action_with_accel(action, '<Ctrl>k')
		actions['goto_pvr_dir'] = action
		
		action = gtk.Action('GotoPCDir', _('Go to PC Location'), _('Go to PC Location'), None)
		actiongroup.add_action_with_accel(action, '<Ctrl>l')
		actions['goto_pc_dir'] = action
		
		actiongroup.add_toggle_actions([('QuitAfterTransfer', None, _('Quit After Transfer'), None, None, self.on_quit_after_transfer),
		                                ('ShowHidden', None, _('Show Hidden Files'), None, _('Show Hidden Files'), self.on_show_hidden_toggled),
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
		
		self.uimanager.add_ui_from_file(datadir + 'guppy-gtk.xml')

		self.file_popup = self.uimanager.get_widget('/FileTreePopup')
		self.file_popup_delete_btn = self.uimanager.get_widget('/FileTreePopup/Delete')
		self.file_popup_mkdir_btn = self.uimanager.get_widget('/FileTreePopup/MakeDir')
		self.file_popup_rename_btn = self.uimanager.get_widget('/FileTreePopup/Rename')
		
		self.file_popup.connect('selection-done', self.on_file_popup_done)
		
		return actions

	def customWidgetHandler(self, glade, func_name, widget_name, str1, str2, int1, int2, *args):
		handler = getattr(self, func_name)
		return handler(str1, str2, int1, int2)
		
	def changeDir(self, fs_model, dir):
		try:
			# Handle directories which have been excluded from PVR file cache.
			if isinstance(fs_model, PVRFileSystemModel):
				dir_abspath = fs_model.abspath(dir)
				if dir_abspath in self.cache_exclusions:
					try:
						fs_model.updateDirectory(dir_abspath, self.cache_exclusions)
					except PuppyBusyError:
						msg = _('Cannot enter the folder ' + dir)
						msg2 = _('It is not possible to enter the folder ' + dir + ' during a file transfer.')
						
						dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
						                           buttons=gtk.BUTTONS_CLOSE,
						                           message_format=msg)
						dialog.format_secondary_text(msg2)
						
						dialog.run()
						dialog.destroy()
						
						return False
				
			return fs_model.changeDir(dir)
		except OSError:
			if dir == None:
				dir = fs_model.getCWD()
			self.showErrorDialog(_('The folder contents could not be displayed.'),
								 _('You do not have the permissions necessary to view the contents of "%s".') % dir)
			return False
		except PVRFileSystemError:
			self.showErrorDialog(_('The folder contents could not be displayed.'),
								 _('Unable to read the contents of "%s". Use your PVR to move the files from "%s" into another folder and try Guppy again.') % (dir,dir))
			return False
			
		
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
		
		self.pvr_path['entry'] = self.glade_xml.get_widget('pvr_path_entry')
		self.pvr_path['entry'].connect('activate', self.on_path_entry_activate, self.pvr_model)
		self.pvr_path['entry'].connect('key-press-event', self.on_path_entry_key_press, self.pvr_path)
		
		self.pc_path['entry'] = self.glade_xml.get_widget('pc_path_entry')
		self.pc_path['entry'].connect('activate', self.on_path_entry_activate, self.pc_model)
		self.pc_path['entry'].connect('key-press-event', self.on_path_entry_key_press, self.pc_path)
		
		self.pvr_path['entry'].set_text(self.pvr_model.getCWD())
		self.pc_path['entry'].set_text(self.pc_model.getCWD())
		
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

	def deleteFiles(self, files, fs_model, warn=True):
		"""Delete files from file system. Popup error dialog for errors.
	
		Return: True if all files deleted.
		"""
		
		if warn:
			msg = _('Are you sure you want to permanently delete')
			
			files_len =  len(files)
			if files_len > 1:
				msg += ' ' + _('the %d selected items?') % files_len
			else:
				msg += ' "%s"?' % files[0]
				
			msg2 = _('If you delete an item, it is permanently lost.')
			
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_WARNING,
			                           buttons=gtk.BUTTONS_CANCEL,
			                           message_format=msg)
			dialog.format_secondary_text(msg2)
			dialog.add_button(gtk.STOCK_DELETE, 0)
			
			response = dialog.run()
			dialog.destroy()
	
			if response == gtk.RESPONSE_CANCEL or response == gtk.RESPONSE_DELETE_EVENT:
				return False
		
		retval = True
		cancel = False
		for name in files:
			if cancel:
				break
			deleted = False
			while not deleted:
				try:
					fs_model.delete(name)
					deleted = True
				except OSError:
					dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
					                           message_format=_('Error while deleting.'))
					dialog.format_secondary_text(_('Cannot delete "%s" because you do not have permissions to change it or its parent folder.') % (fs_model.getCWD() + '/' + name))

					if len(files) > 1:
						dialog.add_button( _('_Skip'), gtk.RESPONSE_REJECT)
					dialog.add_button( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
					dialog.add_button(_('_Retry'), gtk.RESPONSE_ACCEPT)
					dialog.set_default_response(gtk.RESPONSE_ACCEPT)
					response = dialog.run()
					dialog.destroy()
		
					# Skip this file and go to next file
					if response == gtk.RESPONSE_REJECT:
						retval = False
						break
					
					if response == gtk.RESPONSE_CANCEL or \
					   response == gtk.RESPONSE_DELETE_EVENT:
						retval = False
						cancel = True
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
		
		if isinstance(fs_model, PCFileSystemModel):
			path_bar = self.pc_path['bar']
		else:
			path_bar = self.pvr_path['bar']
			
		path_bar.setPath(fs_model.getCWD(), update_btns=False)
		
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
			msg = _('Guppy cannot run because the program Puppy is not available. Please install Puppy.')
			msg += '\n\n' + _('You can download Puppy from') + ' <i>http://sourceforge.net/projects/puppy</i>'
			dialog.set_markup(msg)
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
		dialog.run()
		dialog.destroy()
	
	def on_column_clicked(self, col, data):
		order = col.get_sort_order()
		print order
		if order == gtk.SORT_ASCENDING:
			order = gtk.SORT_DESCENDING
		else:
			order = gtk.SORT_ASCENDING

		col.set_sort_order(order)
		data[0].set_sort_column_id(data[1], order)

	def on_delete_btn_clicked(self, widget, treeview, fs_model, warn=True):
		selection = treeview.get_selection()
		model, rows = selection.get_selected_rows()
		
		if len(rows) == 0:
			return
		
		files = []
		for path in rows:
			iter = model.get_iter(path)
			name = model.get_value(iter, FileSystemModel.NAME_COL)
			files.append(name)
			
		self.deleteFiles(files, fs_model, warn)
			
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

	def on_goto_dir(self, widget, path, fs_model):
		if path['bar']:
			path['bar'].hide()
			path['entry'].set_text(fs_model.getCWD())
			path['entry_box'].show()
		path['entry'].grab_focus()

	def on_mkdir_btn_clicked(self, widget, treeview, fs_model):
		try:
			name = fs_model.mkdir()
		except OSError:
			dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
			                           buttons=gtk.BUTTONS_CLOSE,
			                           message_format=_('Error while creating folder.'))
			dialog.format_secondary_text(_('Cannot create folder because you do not have permission to write in its parent folder.'))
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
				# Handle Permission Denied error				
				if str(error).find('Errno 13') != -1:
					dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
					                           message_format=_('Error while renaming.'))
					dialog.format_secondary_text(_('Cannot rename "%s" because you do not have permissions to change it or its parent folder.') % (fs_model.getCWD() + '/' + old_name))
					dialog.add_buttons(_('_Skip'), gtk.RESPONSE_REJECT,
					                   _('_Retry'), gtk.RESPONSE_ACCEPT)
					response = dialog.run()
					dialog.destroy()
		
					# Skip this file and go to next file
					if response == gtk.RESPONSE_REJECT or \
					   response == gtk.RESPONSE_DELETE_EVENT:
						retval = False
						break
				
					# Try to rename again
					continue
				elif str(error).find('Errno 17') != -1:
					dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
					                           message_format=_('The item could not be renamed.'))
					dialog.format_secondary_text(_('The name "%s" is already used in this folder.') % new_name)
					dialog.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
					                   _('_Replace'), gtk.RESPONSE_APPLY)
					response = dialog.run()
					dialog.destroy()
		
					# Skip this file and go to next path in files
					if response == gtk.RESPONSE_CANCEL or \
					   response == gtk.RESPONSE_DELETE_EVENT:
						break
		
					deleted = self.deleteFiles([new_name], fs_model, False)
					
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

		dir_changed = self.changeDir(fs_model, path)
	
		if dir_changed == False:
			widget.set_text(fs_model.getCWD())
		
		if fs_model == self.pc_model:
			self.updateFreeSpace(self.pc_model)
			if self.no_path_bar_support == False:
				self.pc_path['entry_box'].hide()
				if dir_changed:
					self.pc_path['bar'].setPath(path)
				self.pc_path['bar'].show()
		else:
			if self.no_path_bar_support == False:
				self.pvr_path['entry_box'].hide()
				if dir_changed:
					self.pvr_path['bar'].setPath(path)
				self.pvr_path['bar'].show()

	def on_path_entry_key_press(self, entry, event, path):
		keyname = gtk.gdk.keyval_name(event.keyval)
		# <ESC>: Hide path entry
		if keyname == 'Escape':
			if self.no_path_bar_support == False:
				path['entry_box'].hide()
				path['bar'].show()
				
	def on_pvr_error_btn_clicked(self, widget, data=None):
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
		
		# Only a single file can be renamed at a time.
		if len(files) != 1:
			return
		
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
		
		total_size = 0
		# Don't enable action group unless are files selected.
		enable_actiongrp = False
		for path in files:
			iter = model.get_iter(path)
			type = model.get_value(iter, FileSystemModel.TYPE_COL)
			
			size = model.get_value(iter, FileSystemModel.SIZE_COL)
			if type != 'd':
				total_size += convertToBytes(size)
				enable_actiongrp = True

		msg = _('Selection Size') + ': ' + humanReadableSize(total_size)
		
		if isinstance(fs_model, PCFileSystemModel):
			label = self.pc_total_size_label
			actiongrp = self.upload_actiongrp
		else:
			label = self.pvr_total_size_label
			actiongrp = self.download_actiongrp
			
		label.set_text(msg)
		if enable_actiongrp > 0:
			actiongrp.set_sensitive(True)
		else:
			actiongrp.set_sensitive(False)

	def on_treeview_key_press(self, treeview, event, fs_model):
		keyname = gtk.gdk.keyval_name(event.keyval)
		# <F2>: Rename selected file.
		if keyname == 'F2':
			self.on_rename_btn_clicked(None, treeview, fs_model)
		# <Delete>: Delete selected files.
		elif keyname == 'Delete':
			warn = True
			if event.get_state() & gtk.gdk.SHIFT_MASK:
				warn = False
			self.on_delete_btn_clicked(None, treeview, fs_model, warn)
	
	def on_treeview_row_activated(self, widget, path, col, fs_model):
		model = widget.get_model()
		iter = model.get_iter(path)
		name = model.get_value(iter, FileSystemModel.NAME_COL)
		type = model.get_value(iter, FileSystemModel.TYPE_COL)
		
		if type == 'd':
			self.changeDir(fs_model, name)
			path = fs_model.getCWD()
			if fs_model == self.pc_model:
				if self.no_path_bar_support == False:
					self.pc_path['entry_box'].hide()
					self.pc_path['bar'].setPath(path)
					self.pc_path['bar'].show()
				self.pc_path['entry'].set_text(path)
				self.updateFreeSpace(self.pc_model)
			else:
				if self.no_path_bar_support == False:
					self.pvr_path['entry_box'].hide()
					self.pvr_path['bar'].setPath(path)
					self.pvr_path['bar'].show()
				self.pvr_path['entry'].set_text(path)

	def on_transfer_cancel_btn_clicked(self, widget, file_transfer):
		state = widget.get_data('state')
		if state == 'remove':
			file_transfer.cancel()
			
			progress_box = file_transfer.xml.get_widget('progress_box')
			progress_box.destroy()
		elif state == 'stop':
			if file_transfer == self.last_file_transfer:
				self.last_file_transfer.setQuitAfterTransfer(False)
			self.puppy.cancelTransfer()
			
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

	def on_turbo_toggled(self, widget, data=None):
		self.turbo = widget.get_active()
		
		if self.turbo and self.turbo_warn:
			dialog = gtk.MessageDialog(message_format=_('You cannot use your PVR remote control when Turbo mode is on.'),
			                           type=gtk.MESSAGE_WARNING,
			                           buttons=gtk.BUTTONS_CLOSE)

			checkbox = gtk.CheckButton(_("Warn me when I enable Turbo mode"))
			checkbox.set_active(self.turbo_warn)
			checkbox.connect('toggled', self.on_turbo_warn_toggled)
			checkbox.show()

			dialog.vbox.pack_end(checkbox)
			dialog.run()
			dialog.destroy()

	def on_turbo_warn_toggled(self, widget):
		self.turbo_warn = widget.get_active()
		
	def on_upload_btn_clicked(self, widget, data=None):
		self.transferFile('upload')

	def on_window_delete_event(self, widget, event, data=None):
		self.on_quit(widget, data)
		# Return True to stop event from propagating to default handler
		# which destroys the window.
		return True

	def reallyQuit(self):
		# Save current working directory path
		setConfValue('PC_CWD', self.pc_model.getCWD())
		setConfValue('PVR_CWD', self.pvr_model.getCWD())
		
		gtk.main_quit()

	def showNoFileOperationDialog(self):
		self.showErrorDialog(_('It is not possible to delete, rename, or create folders on the PVR during a file transfer.'))

	def showErrorDialog(self, msg, msg2=None):
		dialog = gtk.MessageDialog(message_format=msg,
		                           type=gtk.MESSAGE_ERROR,
		                           buttons=gtk.BUTTONS_CLOSE)
		if msg2:
			dialog.format_secondary_text(msg2)
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
			msg += _('Do you still want to continue your')
			if direction == 'download':
				msg += ' ' + _('download?')
			else:
				msg += ' ' + _('upload?')
			
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
		file_transfer = None
		for path in files:
			iter = model.get_iter(path)
			
			if model.get_value(iter, FileSystemModel.TYPE_COL) == 'd':
				continue
			
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

			xml = gtk.glade.XML(self.glade_file,
			                    'progress_box',
			                    self.dirname)			                    
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
			cancel_btn = xml.get_widget('transfer_cancel_button')
			cancel_btn.connect('clicked', self.on_transfer_cancel_btn_clicked, file_transfer)
			cancel_btn.set_data('state', 'remove')
			
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
				msg = _('The file "%s" already exists. Would you like to replace it?') % file.dst
				msg2 = _('If you replace an existing file, its contents will be overwritten.')
				dialog = gtk.MessageDialog(type=gtk.MESSAGE_QUESTION,
				                           message_format=msg)
				dialog.format_secondary_text(msg2)
				
				if len(existing_files) > 1:
					dialog.add_button(_('Replace _All'), REPLACE_ALL)
				dialog.add_buttons( _('_Skip'), SKIP, _('_Replace'), REPLACE)
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
			self.pvr_path['bar'].setPath(fs_model.getCWD())
		else:
			self.pc_path['bar'].setPath(fs_model.getCWD())
	
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
						model.updateDirectory(model.getCWD(), self.cache_exclusions)
					else:
						if model.updateCache(exclude=self.cache_exclusions) == False:
							self.pvr_error_btn.show()
							self.pvr_error_window.addError(_('Failed to get list of files on PVR.'), 'PVRFileSystemModel::updateCache() failed.')
				except PuppyNoPVRError:
					raise

			self.changeDir(model, model.getCWD())
			
			# Reselect rows
			for path in selected_rows[1]:
				selection.select_path(path)

			# Call signal handler explicitly because it will not be called if no
			# rows are reselected, i.e. not paths in selected_rows[] are valid.
			self.on_treeview_changed(selection, model)
			
			selection.handler_unblock(handler_id)

if __name__ == "__main__":
	locale.setlocale(locale.LC_ALL, '')
	gettext.bindtextdomain(APP_NAME, 'i18n')
	gettext.textdomain(APP_NAME)
	gettext.install(APP_NAME, 'i18n', unicode=1)
	
	guppy = GuppyWindow()
	guppy.run()
