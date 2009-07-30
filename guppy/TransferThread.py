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

import threading

import gtk

import GuppyWindow

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
		
			cancel_btn = xml.get_widget('transfer_cancel_button')	

			gtk.gdk.threads_enter()
			allocation = cancel_btn.get_allocation()
			cancel_btn.set_label(gtk.STOCK_STOP)
			cancel_btn.set_size_request(allocation.width, allocation.height)
			cancel_btn.set_data('state', 'stop')
			gtk.gdk.threads_leave()

			progress_bar = xml.get_widget('transfer_progressbar')
			
			# Keep trying puppy operation until we succeed or there is an error.
			while True:
				try:
					# Enable turbo mode if required
					if self.guppy.turbo == True:
						self.guppy.puppy.setTurbo(True)
					
					if direction == 'download':
						self.guppy.puppy.getFile(src_file, dst_file)
					else:
						self.guppy.puppy.putFile(src_file, dst_file)
					
					break
				except PuppyBusyError:
					time.sleep(5)
					continue
				except PuppyError:
					break			

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
					except PuppyError, error:
						transfer_error = error
						pass

					continue

				# Transfer may have completed
				if percent is None:
					break
					
				gtk.gdk.threads_enter()
				progress_bar.set_fraction(float(percent)/100)
				progress_bar.set_text('(' + transfer_time['remaining'] + ' ' + _('Remaining') + ')')
				gtk.gdk.threads_leave()

			# Disable turbo mode. The PVR remote control cannot be used if
			# turbo mode is left on.
			if self.guppy.turbo == True:
				self.guppy.puppy.setTurbo(False)

			# Set modification time of downloaded file to the same time
			# as on the PVR.
			if transfer_successful and direction == 'download':
				try:
					# Parse date string
					time_struct = time.strptime(file_transfer.file_date, '%a %b %d %Y')
					
					# Convert to seconds since the epoch
					time_secs = time.mktime(time_struct)
					
					# Set modification time
					os.utime(dst_file, (int(time.time()), time_secs))
				except:
					pass
			
			gtk.gdk.threads_enter()
			if transfer_successful:
				progress_bar.set_fraction(1)

				progress_bar.set_text(_('Finished'))
			else:
				progress_bar.set_text(_('Transfer Failed'))
				self.guppy.pvr_error_btn.show()

				if direction == 'download':
					separator = '\\'
					msg = _('Failed to download:') + '\n'
				else:
					separator = '/'
					msg = _('Failed to upload:') + '\n'

				idx = src_file.rfind(separator)
				if idx > 0:
					msg += src_file[idx+1:]
				else:
					msg += src_file
				
				self.guppy.pvr_error_window.addError(msg, transfer_error)

			gtk.gdk.threads_leave()
				

			# Desensitise all widgets			
			for widget in ['progress_hbox1', 'progress_hbox2']:
				widget = xml.get_widget(widget)
				gtk.gdk.threads_enter()
				widget.set_sensitive(False)
				gtk.gdk.threads_leave()

			# Change Stop button to Remove button
			gtk.gdk.threads_enter()
			cancel_btn.set_data('state', 'remove')
			cancel_btn.set_label(gtk.STOCK_REMOVE)
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
