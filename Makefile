DESTDIR=/usr/local

install:
	python setup.py install --prefix=$(DESTDIR)

clean:
	python setup.py clean

dist:
	python setup.py sdist --formats=bztar
	# Make Fedora RPM
	ln -sf setup.cfg-fedora setup.cfg
	python setup.py bdist_rpm
	# Make SUSE RPM
# Broken at the moment :(
#	ln -sf setup.cfg-suse setup.cfg
#	python setup.py bdist_rpm
#	rm -f setup.cfg

.PHONY: install clean dist
