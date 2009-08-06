DESTDIR=/usr/local
DESTDIR=/local/will_be_removed/guppy-install
DEB_BUILD_DIR=build/deb
VERSION=$(shell python -c 'import guppy.about; print guppy.about.VERSION')
DIST_DIR=dist

puppy:
	(cd puppy && $(MAKE))

install:
	python setup.py install --prefix=$(DESTDIR)

clean:
	python setup.py clean
	rm -f guppy/*.pyc
	rm -rf build $(DIST_DIR) MANIFEST
	(cd puppy && $(MAKE) clean)

dist:
	python setup.py sdist --formats=bztar

rpm:
	python setup.py bdist_rpm --install-script pkg/fedora_bdist_rpm-install.spec --force-arch=$(shell uname -m)

deb:
	# Make build area
	rm -rf $(DEB_BUILD_DIR)
	mkdir -p $(DEB_BUILD_DIR)/DEBIAN
	cp pkg/guppy.control $(DEB_BUILD_DIR)/DEBIAN/control
	mkdir -p $(DIST_DIR)

	# Install into build area
	python setup.py install --prefix=$(DEB_BUILD_DIR)/usr

	# Move HAL script to directory appropriate for Debian systems
	mkdir -p $(DEB_BUILD_DIR)/usr/share/hal/scripts/
	mv $(DEB_BUILD_DIR)/usr/libexec/hal-* $(DEB_BUILD_DIR)/usr/share/hal/scripts/
	rm -rf $(DEB_BUILD_DIR)/usr/libexec

	# Build the deb
	dpkg --build $(DEB_BUILD_DIR) $(DIST_DIR)/guppy_$(VERSION)_all.deb

.PHONY: install clean dist rpm deb puppy
