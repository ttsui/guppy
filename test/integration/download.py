#!/usr/bin/python

from dogtail import tree
from dogtail.utils import run
from dogtail.predicate import GenericPredicate

run('guppy')

guppy = tree.root.application('guppy')

guppy.keyCombo("<Control>k")

pvrPathEntry = guppy.textentry('PVR Path Entry')
pvrPathEntry.typeText("\DataFiles")
pvrPathEntry.keyCombo("Return")

guppy.keyCombo("<Control>l")
pcPathEntry = guppy.textentry('PC Path Entry')
pcPathEntry.typeText("/local/will_be_removed")
pcPathEntry.keyCombo("Return")

pvrTree = guppy.child('PVR Tree')
pvrTree.child('FAT PIZZA-#.rec', roleName='table cell').click()

guppy.button('Download').click()

assert guppy.child('Progress Bar').text == 'Finished'

transferFileNameLabel = guppy.childLabelled('FAT PIZZA-#.rec')
progressBox = transferFileNameLabel.findAncestor(GenericPredicate('Transfer Progress Box'))
assert progressBox.child('Progress Bar').text == 'Finished'
