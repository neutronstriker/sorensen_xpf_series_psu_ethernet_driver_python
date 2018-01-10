# -*- coding: utf-8 -*-
"""
Created on Sat Oct 07 19:42:18 2017

Sorensen PSU Socket Based Ethernet Interface Driver.

@author: Srinivas N
Description: This is the Driver module for Sorensen PSU Ethernet interface.
This had to be designed because pyvisa-py was not able to process any query or read methods.
Only write methods were working in pyvisa-py.

"""

SORENSEN_IP = "10.236.76.92"
SORENSEN_SOCKET_SERVER_PORT = 9221

READ_WRITE_TIMEOUT = 3#seconds
READ_TERMINATION_CHAR = '\r'
WRITE_TERMINATION_CHAR = '\n'



import socket
import time
import requests

'''
def createConnection(Ip,Port):
    session = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    session.connect((str(Ip),int(Port)))
    return session

def write(socketSession,message):
    socketSession.sendall(str(message)+'\n')
    
def read(socketSession,size):
    data = socketSession.recv(int(size))
    return data

def query(socketSession,queryCmd,delayValue=0,responseTermChar=None):
    socketSession.sendall(str(queryCmd)+'\n')
    if(delayValue):
        time.sleep(delayValue)
    return socketSession.recv(1)


if __name__ == '__main__':
    session = createConnection(SORENSEN_IP,SORENSEN_SOCKET_SERVER_PORT)
    write(session,'OP1 0')
    session.close()
'''    


class SorensenSocketInterfaceDriver:
    def __init__(self,Ip,Port=SORENSEN_SOCKET_SERVER_PORT):
        self.devIp = Ip
        self.connectionCreated = False
        try:
            self.sessionInstance = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            self.sessionInstance.settimeout(READ_WRITE_TIMEOUT)
            self.sessionInstance.connect((str(self.devIp),Port))
        except Exception as e:
            print 'Failed to create a Connection, Check Device IP'
            print 'Exception Details:'
            print str(e)
            return None
        self.connectionCreated = True
        
    
    def write(self,message):
        if(self.connectionCreated):
            self.sessionInstance.sendall(str(message)+WRITE_TERMINATION_CHAR)
        else:
            print 'Connection Does not exist, reinit this object with Proper Device Ip.'
            
    def read(self,terminationChar=READ_TERMINATION_CHAR):
        if(self.connectionCreated):
            data = ''            
            while True:
                try:                
                    receivedChar = self.sessionInstance.recv(1)
                except Exception as e:
                    print 'There has been an Exception in read(), find details below:'
                    print str(e)
                    return data.strip('\n')
                if receivedChar == terminationChar:
                    return data.strip('\n')
                data = data + receivedChar                    
    
    def readBlock(self,size):
        #I found that even if we give a defined block size, the recv() returns if it finds some data
        #but only when the it has received either all data or if it has received "size" bytes
        #so that means I can just have one read function instead of playing safe by reading 1 byte
        #at a time I can call this and trim the trailing termination char
        if(self.connectionCreated):
            try:                
                receivedBlock = self.sessionInstance.recv(size)
                return receivedBlock
            except Exception as e:
                print 'There has been an Exception in readBlock(), find details below:'
                print str(e)
                return ''

            
    def query(self,cmd,delayValue=None):
        #need to keep in place a query validation mechanism, to make sure
        #that we don't send a cmd which doesn't yield any output to be read.
        #I think a place to start with is checking if the 'cmd' has a trailing '?'.
        #Also need to place a mechanism where we can detect an Invalid command, i.e.
        #a command not understood by the device.
        #also need to clear the received data buffer to make sure we are reading response
        #from current command only and not some previous command
        #actually clearing buffer may not be required because the PSU core follows
        #a LIFO principle of output data buffer.
        self.write(cmd)
        if (delayValue):
            time.sleep(delayValue)
        return self.read()

    #block read driver needs to be worked on
    def query_new(self,cmd,delayValue=None):
        self.write(cmd)
        if (delayValue):
            time.sleep(delayValue)
        data = self.readBlock(4096)
        #print data
        lines = data.split(READ_TERMINATION_CHAR)
        #the output buffer is LIFO type so reading the 1st line gives us our
        #data, but sometimes there is a issue which is that it reads before
        #this cmd has been executed by the PSU, so we get previous data.
        #This can be fixed by providing a delay in the argument, but a better
        #way would be to reset the buffer before providing any commands.
        return lines[0]
        
    def closeConnection(self):
        self.connectionCreated = False        
        self.sessionInstance.close()
        
    def __del__(self):
        self.closeConnection()
    

class SorensenWebInterfaceDriver:
    def __init__(self,IP):
        self.IP = IP
        
    def InstrumentHighlight(self):
        r = requests.post('http://'+self.IP+'/home.cgi',data={'pg':'id','set':'Identify Instrument'})
        if r.status_code == 200:
            return 1
        else:
            return -1
    def InstrumentDeHighlight(self):
        r = requests.post('http://'+self.IP+'/home.cgi',data={'pg':'id','set':'Turn off Identify Instrument'})
        if r.status_code == 200:
            return 1
        else:
            return -1
    def InstrumentQuery(self,queryString):
        r = requests.post('http://'+self.IP+'/control.cgi',data={'cmd':str(queryString),'pg':'ctrl','set':'Submit'})
        if r.status_code == 200 and r.text.find('Reply') != -1:        
            queryResponse = r.text.split('Reply')[1].split('<PRE>')[1].split('</PRE>')[0].strip('\r\n')
            return queryResponse
        else:
            return 'Error!'
    def InstrumentWrite(self,cmdString):
        r = requests.post('http://'+self.IP+'/control.cgi',data={'cmd':str(cmdString),'pg':'ctrl','set':'Submit'})
        if r.status_code == 200:        
            return 1
        else:
            return -1

class SorensenPSUviaEth:
    def __init__(self,psuIP,driver=SorensenWebInterfaceDriver):
        self.IP= psuIP
        self._driver = driver
        if self._driver != SorensenSocketInterfaceDriver and self._driver != SorensenWebInterfaceDriver:
            raise 'DriverNotSpecified'#need to fix this

        self._driverSession = driver(self.IP)

        if self._driver == SorensenSocketInterfaceDriver:
            self.query = self._driverSession.query
            self.write = self._driverSession.write
        else:
            self.query = self._driverSession.InstrumentQuery
            self.write = self._driverSession.InstrumentWrite
        
        
    def getVoltage_Set(self,channel):
        data = self.query('V'+str(channel)+'?')
        return float(data.split('V'+str(channel))[1].strip(' '))

    def getVoltage_Measured(self,channel):
        data = self.query('V'+str(channel)+'O?')
        return float(data.strip('V'))

    def getCurrent_Measured(self,channel):
        data = self.query('I'+str(channel)+'O?')
        return float(data.strip('A'))

    def getCurrent_Set(self,channel):
        data = self.query('I'+str(channel)+'?')
        return float(data.split('I'+str(channel))[1].strip(' '))
    
    def setVoltage(self,channel,Volts):
        self.write('V'+str(channel)+' '+str(Volts))
    
    def setCurrent(self,channel,Current):
        self.write('I'+str(channel)+' '+str(Current))
        
    def setOVPlimit(self,channel,Volts):
        self.write('OVP'+str(channel)+' '+str(Volts))

    def getOVPlimit(self,channel):
        data = self.query('OVP'+str(channel)+'?')
        return float(data.split('VP'+str(channel))[1].strip(' '))

    def setOCPlimit(self,channel,Current):
        self.write('OCP'+str(channel)+' '+str(Current))

    def getOCPlimit(self,channel):
        data = self.query('OCP'+str(channel)+'?')
        return float(data.split('CP'+str(channel))[1].strip(' '))

    def channelOn(self,channel):
        self.write('OP'+str(channel)+' 1')

    def channelOff(self,channel):
        self.write('OP'+str(channel)+' 0')
    
    def allChannelOFF(self):
        self.write('OPALL 0')
        
    def allChannelON(self):
        self.write('OPALL 1')

    def getChannelState(self,channel):
        data = self.query('OP'+str(channel)+'?')
        if int(data) == 0:
            return 0
        elif int(data) == 1:
            return 1
        else:
            return -1 #this means error

    def toggle_ID_Flashing(self):
        _P_ = SorensenWebInterfaceDriver(self.IP)
        _P_.InstrumentHighlight()

    def __del__(self):
        if self._driver == SorensenSocketInterfaceDriver:
            self._driverSession.closeConnection()

if __name__ == '__main__':
    
    print 'Socket Interface Demo..'
    SPSU = SorensenSocketInterfaceDriver(SORENSEN_IP)
    print SPSU.query('*IDN?')
    SPSU.write('OP1 0')
    print SPSU.query('V1?')
    SPSU.closeConnection()
    
    print 'Now starting WebInterface Demo'
    PSU = SorensenWebInterfaceDriver(SORENSEN_IP)
    print PSU.InstrumentWrite('OP1 0')
    print PSU.InstrumentQuery('OP1?')
    print PSU.InstrumentQuery('V1?')
