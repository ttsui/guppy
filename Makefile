# Guppy Makefile to create source distribution
#
VERSION = 0.0.2
SRC = src/guppy.py src/puppy.py src/guppy.glade src/guppy-gtk.xml
FILES = COPYING README AUTHORS NEWS
BUILD_DIR = dist/guppy-$(VERSION)

dist: $(SRC) $(FILES)
	mkdir -p $(BUILD_DIR)
	cp $^ $(BUILD_DIR)
	tar jcf guppy-$(VERSION).tar.bz2 -C dist guppy-$(VERSION)

clean:
	rm -rf guppy-$(VERSION).tar.bz2 dist/
