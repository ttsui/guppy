import mox

import popen2

from puppy import Puppy
	
def ignoresPacketCRCErrors_test():
	mocker = mox.Mox()

	mocker.StubOutWithMock(popen2, 'Popen4', True)
	
	popen = mocker.CreateMockAnything()
	popen.tochild = mocker.CreateMockAnything()
	popen.tochild.close()
	popen.poll().AndReturn(-1)
	popen.poll().AndReturn(-1)
	
	popen2.Popen4([ 'puppy', '-i', '-c', 'get', 'movie.rec', 'movie.rec' ]).AndReturn(popen)
	
	mocker.ReplayAll()

	puppy = Puppy()
	puppy.getFile('movie.rec', 'movie.rec')
	
	mocker.VerifyAll()
