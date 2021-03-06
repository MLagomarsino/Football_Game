# To track the ball with the camera - launch raspicam before!

#!/usr/bin/env python
# Python libs
import sys, time

# numpy and scipy
import numpy as np
from scipy.ndimage import filters

import imutils

# OpenCV
import cv2

# Ros libraries
import roslib
import rospy

# Ros Messages
from sensor_msgs.msg import CompressedImage
from geometry_msgs.msg import Point
## @file
VERBOSE = False

## Class to acquire image from the camera
#
# The class performs:
# 	* object segmentation based on color to detect the ball;
#	* tracking of ball centroid;
#	* publish current coordinates of the ball centroid on /ball_coord
class image_feature:

	## Init
	#
	# * publish the coordinates of the ball wrt to the robot frame on /ball_coord
	# * publish the compressed image from the camera on /output/image_raw/compressed
	# * subscribe to /raspicam_node/image/compressed to acquire the compressed image of the camera
    def __init__(self):
		# topic where we publish the coordinates of the ball wrt to the robot frame
		self.ball_coord = rospy.Publisher("/ball_coord", Point, queue_size = 1)
		# topic where we publish the compressed image from the camera
		self.image_pub = rospy.Publisher("/output/image_raw/compressed", CompressedImage, queue_size = 1)

		# topic of the compressed image of the camera to which we subscribe
		self.subscriber = rospy.Subscriber("/raspicam_node/image/compressed", CompressedImage, self.callback,  queue_size = 1)
		if VERBOSE :
			print "subscribed to /raspicam_node/image/compressed"

	## Callback function of subscribed topic /raspicam_node/image/compressed
	#
    # Here images get converted and features detected.
    def callback(self, ros_data):
        
        if VERBOSE :
            print('received image of type: "%s"' % ros_data.format)

        #### direct conversion to CV2 ####
        np_arr = np.fromstring(ros_data.data, np.uint8)
        image_np = cv2.imdecode(np_arr, cv2.IMREAD_COLOR) # OpenCV >= 3.0:

	# data from camera calibration
	camera_matrix = [[239.311758, 0, 156.442041],
                     [0, 238.756569, 120.177064],
                     [0, 0, 1]]

	distortion_coeff = [[0.107782,
	                   -0.225106,
	                    0.003817,
	                   -0.006264, 
	                    0]]
	           
    # set of ball points
	objectPoints = np.zeros((5,3))
	objectPoints[0] = (0, 0, 0)
	objectPoints[1] = (-27, 0, 0)
	objectPoints[2] = (27, 0, 0)
	objectPoints[3] = (0, 17, 0)
	objectPoints[4] = (0, -17, 0)

	# range of color to detect the ball
	# greenLower = (20, 50, 20)
	# greenUpper = (40, 255, 255)
	
	blueLower = (100, 150, 0)
	blueUpper = (140, 255, 255)

	blurred = cv2.GaussianBlur(image_np, (11, 11), 0)
	hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
	mask = cv2.inRange(hsv, blueLower, blueUpper)
	mask = cv2.erode(mask, None, iterations = 2)
	mask = cv2.dilate(mask, None, iterations = 2)
	#cv2.imshow('mask', mask)
	cnts = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	cnts = imutils.grab_contours(cnts)
	center = None
	# only proceed if at least one contour was found
	if len(cnts) > 0:
		# find the largest contour in the mask, then use
		# it to compute the minimum enclosing circle and
		# centroid
		c = max(cnts, key = cv2.contourArea)
		((x, y), radius) = cv2.minEnclosingCircle(c)
		M = cv2.moments(c)
		center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
 
		# only proceed if the radius meets a minimum size
		if radius > 10:
			# draw the circle and centroid on the frame,
			# then update the list of tracked points
			cv2.circle(image_np, (int(x), int(y)), int(radius), (0, 255, 255), 2)
			cv2.circle(image_np, center, 5, (0, 0, 255), -1)
 			
			# corresponding points in the image plane
			imagePoints = np.zeros((5, 2))
			imagePoints[0] = (x, y)
			imagePoints[1] = (x + radius/2, y)
			imagePoints[2] = (x - radius/2, y)
			imagePoints[3] = (x, y - radius/2)
			imagePoints[4] = (x, y + radius/2)

			# function to obtain the 3D coordinates of the ball centroid
			retval, rvec, tvec = cv2.solvePnP(objectPoints, imagePoints, np.asarray(camera_matrix), np.asarray(distortion_coeff), False, cv2.SOLVEPNP_EPNP)
			if(tvec.all() is not None): # Output translation vector of centroid wrt camera
				print(tvec)
				ball_centroid  = Point(x = tvec[0], y = tvec[1], z = tvec[2])
				# publish ball coordinates on /ball_coord
				self.ball_coord.publish(ball_centroid)
			
			print(tvec)
			ball_centroid  = Point(x = tvec[0], y = tvec[1], z = tvec[2])
		
		else:  #the robot does not see the ball
			ball_centroid  = Point(x = 0, y = 0, z = 0)

		self.ball_coord.publish(ball_centroid)
		
		# update the points queue
		# pts.appendleft(center)
        cv2.imshow('window', image_np)
        cv2.waitKey(2)
        
		# for n in range(0, 1000000):
		# rec()		

        # self.subscriber.unregister()

def main(args):

    ic = image_feature()
    rospy.init_node('image_feature', anonymous=True)
    
	try:
        rospy.spin()
    except KeyboardInterrupt:
        print("Shutting down ROS Image feature detector module")
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main(sys.argv)
