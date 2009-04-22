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

import os

import gtk
import gobject

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
		for widget in [ self.down_btn, self.up_btn ] + self.btn_list:
			widget.size_request()
		
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
		# Deactivate toggle button because the changeDir() may fail. If
		# changeDir() is successfull updatePathBtns() will activate the toggle
		# button.
		handler = widget.get_data('handler_id')
		widget.handler_block(handler)
		widget.set_active(False)
		widget.handler_unblock(handler)
		
		if self.fs == 'pvr':
			path = path.replace('/', '\\')
			if self.guppy.changeDir(self.guppy.pvr_model, path) is False:
				return
			self.guppy.pvr_path['entry'].set_text(path)
		else:
			if self.guppy.changeDir(self.guppy.pc_model, path) is False:
				return
			self.guppy.pc_path['entry'].set_text(path)

		self.updatePathBtns(path)

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
		
	def setPath(self, path, update_btns=True):
		path = path.replace('\\', '/')
		path = os.path.normpath(path)
		# os.path.normpath() doesn't normalise '//' to '/'
		if path == '//':
			path = '/'
		
		# Check if we are changing to a dir on the same path
		if update_btns and self.updatePathBtns(path):
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
		path = path.replace('\\', '/')
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

