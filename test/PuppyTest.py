import mox

from puppy import Puppy
	
def ignoresPacketCRCErrors_test():
	mocker = mox.Mox()
	
	puppy = Puppy()
	
	mocker.StubOutWithMock(puppy, 'getStatus')
	puppy.getStatus(wait=False).AndReturn(-1)
	
	mocker.StubOutWithMock(puppy, '_execute')
	puppy._execute([ '-i', '-c', 'get', 'movie.rec', 'movie.rec' ])
	
	mocker.ReplayAll()

	puppy.getFile('movie.rec', 'movie.rec')
	
	mocker.VerifyAll()
