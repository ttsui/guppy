DESTDIR=/usr/local
DEB_BUILD_DIR=build/deb
VERSION=guppy-$(shell python -c 'import guppy.about; print guppy.about.VERSION')
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
	mkdir -p $(DIST_DIR)
	git archive --format=tar --prefix=$(VERSION)/ $(VERSION) | bzip2 > dist/$(VERSION).tar.bz2

rpm:
	python setup.py bdist_rpm --install-script pkg/fedora_bdist_rpm-install.spec --force-arch=$(shell uname -m)

.PHONY: install clean dist rpm deb puppy
