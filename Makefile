DESTDIR=/usr

install:
	python setup.py install --prefix=$(DESTDIR)

clean:
	python setup.py clean

dist:
	python setup.py bdist_rpm
	python setup.py sdist --formats=bztar

.PHONY: install clean dist
