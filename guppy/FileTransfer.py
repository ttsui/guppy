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
		
