import rospy
import serial
import time
import threading

from geometry_msgs.msg import Point

startMarker = '<'
endMarker = '>'
dataStarted = False
dataBuf = ""
messageComplete = False
oldRPS = "+0.0 +0.0 +0.0 +0.0"

def rec():
    arduinoReply = recvLikeArduino()
    if not (arduinoReply == 'XXX'):
        print("Time %s  Reply %s" % (time.time(), arduinoReply))


def setupSerial(baudRate, serialPortName):
    global serialPort
    serialPort = serial.Serial(port=serialPortName, baudrate=baudRate, timeout=0, rtscts=True)
    print("Serial port " + serialPortName + " opened  Baudrate " + str(baudRate))
    waitForArduino()


def sendToArduino(stringToSend):

    # this adds the start and end-markers before sending
    global startMarker, endMarker, serialPort

    stringWithMarkers = (startMarker)
    stringWithMarkers += stringToSend
    stringWithMarkers += (endMarker)
    serialPort.write(stringWithMarkers.encode('utf-8'))  # encode needed for Python3
    print(stringToSend)


def recvLikeArduino():

    global startMarker, endMarker, serialPort, dataStarted, dataBuf, messageComplete

    if serialPort.inWaiting() > 0 and messageComplete == False:
        x = serialPort.read().decode("utf-8") # decode needed for Python3

        if dataStarted:
            if x != endMarker:
                dataBuf = dataBuf + x
            else:
                dataStarted = False
                messageComplete = True
        elif x == startMarker:
            dataBuf = ''
            dataStarted = True

    if messageComplete:
        messageComplete = False
        return dataBuf
    else:
        return "XXX"


def waitForArduino():

    # wait until the Arduino sends 'Arduino is ready' - allows time for Arduino reset
    # it also ensures that any bytes left over from a previous message are discarded

    print("Waiting for Arduino to reset")

    msg = ""
    while msg.find("Arduino is ready") == -1:
        msg = recvLikeArduino()
        if not (msg == 'XXX'):
            print(msg)


def callback(msg):
 
    x = msg.x
    z = msg.z
    print(x)
    print(z)
    global oldRPS
    
    if(x > 250): 
        newRPS = "+0.2 +0.2 -0.2 -0.2"
        if(oldRPS == "+0.2 +0.2 +0.2 +0.2" and x > 400):
            # old is go straight
            sendToArduino(newRPS)
            oldRPS = newRPS
            
    elif(x < -250):
        newRPS = "-0.2 -0.2 +0.2 +0.2"
        if(oldRPS == "+0.2 +0.2 +0.2 +0.2" and x > 400):
            sendToArduino(newRPS)
            oldRPS = newRPS
    else:
        if(z > 200):
            newRPS = "+0.2 +0.2 +0.2 +0.2"
            if(newRPS != oldRPS):
                sendToArduino(newRPS)
                oldRPS = newRPS 
        else:
            newRPS = "+0.0 +0.0 +0.0 +0.0"
            if(newRPS != oldRPS):
                sendToArduino(newRPS)
                oldRPS = newRPS

setupSerial(115200, "/dev/ttyACM0")
rospy.init_node('compute_vel')
subscriber = rospy.Subscriber("/ball_coord", Point, callback)
   
rospy.spin()
   
