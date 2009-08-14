## GuppyWindow.py - Main Window
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

import time

import gtk
import gtk.glade
import gobject

class PVRErrorWindow:
	ICON_COL, ICON_SIZE_COL, MSG_COL, OUTPUT_COL = range(4)
	LIST_TYPES = []
	LIST_TYPES.insert(ICON_COL, gobject.TYPE_STRING)
	LIST_TYPES.insert(ICON_SIZE_COL, gobject.TYPE_UINT)
	LIST_TYPES.insert(MSG_COL, gobject.TYPE_STRING)
	LIST_TYPES.insert(OUTPUT_COL, gobject.TYPE_STRING)

	def __init__(self, glade_file, dirname):
		glade_xml = gtk.glade.XML(glade_file,
		                          'pvr_error_window',
		                          dirname)
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

