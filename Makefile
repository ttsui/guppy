DESTDIR=/usr/local
DEB_BUILD_DIR=build/deb
VERSION=$(shell python -c 'import guppy.about; print guppy.about.VERSION')
DIST_DIR=dist
GIT_EXPORT=git archive --format=tar --prefix=guppy-$(VERSION)/ guppy-$(VERSION)

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
	mkdir -p $(DIST_DIR)
	$(GIT_EXPORT) | bzip2 > dist/guppy-$(VERSION).tar.bz2

rpm:
	python setup.py bdist_rpm --install-script pkg/fedora_bdist_rpm-install.spec --force-arch=$(shell uname -m)

deb:
	mkdir -p $(DEB_BUILD_DIR)
	$(GIT_EXPORT) | gzip > $(DEB_BUILD_DIR)/guppy_$(VERSION).orig.tar.gz
	tar zxf $(DEB_BUILD_DIR)/guppy_$(VERSION).orig.tar.gz -C $(DEB_BUILD_DIR)
	cp -ra pkg/debian $(DEB_BUILD_DIR)/guppy-$(VERSION)/
	cd $(DEB_BUILD_DIR)/guppy-$(VERSION)/ && debuild -S -sa

.PHONY: install clean dist rpm deb puppy
