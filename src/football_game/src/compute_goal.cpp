#include "ros/ros.h"
#include "nav_msgs/Odometry.h" // used for the robot goal position
#include "std_msgs/Bool.h" // for the ack message

#include <string>
#include <fstream>
#include <iostream>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "football_game/ReachGoal.h"

#include <geometry_msgs/Vector3.h>
#include <tf/transform_listener.h>
#include <tf/transform_datatypes.h>
#include <tf/transform_broadcaster.h>
#include <math.h>

using namespace std;


/*@file */
ros::Publisher pub_goal; /*!< Publisher of the goal of the robot on /goal*/
ros::Subscriber odom_sub; /*!< Subscriber to /odom*/
nav_msgs::Odometry robot_des; /*!< Odometry message describing the desired position of robot*/

geometry_msgs::Vector3 ball_football_direction; /**< direction between ball and football goal */

float x_ball; /**< x coordinate of the ball */
float y_ball; /**< y coordinate of the ball */

float x_robot; /**< x coordinate of the robot */
float y_robot; /**< y coordinate of the robot */
geometry_msgs::Quaternion orientation_robot;
float yaw;

tf::Transform world2ball; /**< computed transform between the ball and the world */

class BallPositionWorld {
public:
    /**
     * Transformation from world to ball frame
     */
    tf::TransformListener listener;
     
    /** Handler:
     * - subscribe to /ball_coord to read the position of the ball
     * - subscribe to /odom topic to read robot odometry
     */
    BallPositionWorld()
    {
        ball_pos_sub = nh.subscribe("/ball_coord", 10, &BallPositionWorld::ballPosCallback, this);
		odom_sub = nh.subscribe("/odom", 1000, &BallPositionWorld::odomCallback, this);
    }

	/** Callback associated to topic /odom
	 * @param[in]  msg		odometry message, namely current position of robot */
	void odomCallback(const nav_msgs::Odometry& msg)
	{
		x_robot = msg.pose.pose.position.x; /**< x coordinate of the robot */
		y_robot = msg.pose.pose.position.y; /**< y coordinate of the robot */
		orientation_robot = msg.pose.pose.orientation; /**< Orientation of the robot wrt the world frame*/
	}
    /** 
     * Callback function
     * @param[in]  ball_pos position of the ball wrt the camera -(if not published from terminal)-
     */
    void ballPosCallback(const geometry_msgs::Point &ball_pos)
	{
		x_ball = ball_pos.x;
		y_ball = ball_pos.z;

		try{    
			listener.waitForTransform("football_goal_frame","world_frame",  ros::Time(0), ros::Duration(10.0) );
			listener.lookupTransform("football_goal_frame","world_frame", ros::Time(0), t_football_goal2world);
			
			try{    
				listener.waitForTransform("world_frame", "robot_frame", ros::Time(0), ros::Duration(10.0) );
				listener.lookupTransform("world_frame", "robot_frame",  ros::Time(0), t_world2robot);

				try{    
					listener.waitForTransform("robot_frame", "ball_frame", ros::Time(0), ros::Duration(10.0) );
					listener.lookupTransform("robot_frame", "ball_frame",  ros::Time(0), t_robot2ball);
					tf::Transform robot2ball(t_robot2ball.getBasis(), t_robot2ball.getOrigin());
					world2ball = t_world2robot * robot2ball;

					tf::Transform football_goal2ball = t_football_goal2world * world2ball;
					tf::Vector3 ball_football_direction;
					ball_football_direction = football_goal2ball.getOrigin();

					// compute yaw angle between football goal and the ball, usefull to kick the ball
					yaw = atan((ball_football_direction.getX())/(ball_football_direction.getY() - 2.0));
				}
				catch (tf::TransformException &ex){
					ROS_WARN("World to robot transform unavailable %s", ex.what());
				}
			}
			catch (tf::TransformException &ex){
				ROS_WARN("World to robot transform unavailable %s", ex.what());
			}
		}
		catch (tf::TransformException &ex){
			ROS_WARN("Robot to ball transform unavailable %s", ex.what());
		}	
}

protected:
	tf::StampedTransform t_world2robot;	/**< Transformation from world_frame to robot_frame*/
	tf::StampedTransform t_football_goal2world;	/**< Transformation from football_goal_frame to world_frame*/
	tf::StampedTransform t_robot2ball; /**< Transformation from robot_frame to ball_frame*/

    ros::NodeHandle nh;		/**< Node Handler */
    ros::Subscriber ball_pos_sub; /**< Subscriber to /ball_coord */
};

/** The function:
 * - acquires the initial position of the robot (robot_des of the previous loop)
 * @param[out]  robot_des	odometry message specifing the desired robot position
 */
nav_msgs::Odometry compute_plan()
{
	tf::Vector3 ball_point(x_ball, y_ball, 0);
	tf::Vector3 ball_wrt_world;
	// ball wrt world frame
	// ball_wrt_world = world2ball * ball_point; // ONLY WHEN USING THE REAL ROBOT (the position of the ball is published wrt robot frame) 
	ball_wrt_world = ball_point;

	double r = 0.5; // radius from the ball
	robot_des.pose.pose.position.x = ball_wrt_world.getX() + r*sin(yaw);
	robot_des.pose.pose.position.y = ball_wrt_world.getY() + r*cos(yaw);
	robot_des.pose.pose.position.z = 0;
	// std::cout<<"robot des pos x "<<robot_des.pose.pose.position.x<<"\n";
	// std::cout<<"robot des pos y "<<robot_des.pose.pose.position.y <<"\n";

	tf::Quaternion quat;
	quat.setRPY(0,0,yaw);
	robot_des.pose.pose.orientation.x = quat.x();
	robot_des.pose.pose.orientation.y = quat.y();
	robot_des.pose.pose.orientation.z = quat.z();
	robot_des.pose.pose.orientation.w = quat.w();

	return robot_des;
}

/**
 * Main function:
 *
 * - definition of the publisher of the /goal topic where the goal position of the robot is published
 * - declare and call the reach_goal service 
 * @param[in]  r_x			x coordinate of the robot
 * @param[in]  r_y			y coordinate of the robot
 */
int main(int argc, char ** argv) 
{
	ros::init(argc, argv, "compute_goal");
	ros::NodeHandle n;
	ros::ServiceClient client_reach_goal;
	BallPositionWorld handler;
	bool result = false;
	
	// Declare variables for the initial positions of the robot
	int r_start_x, r_start_y;

	// Get the initial position of the robot from the parameter server
	n.getParam("r_x", r_start_x);
	n.getParam("r_y", r_start_y);

	// Publisher of the goal position
	pub_goal = n.advertise<nav_msgs::Odometry>("/goal", 1);
	
	client_reach_goal = n.serviceClient<football_game::ReachGoal>("/reach_goal");
    	
	ros::Rate r(10000);

	while(ros::ok()){
		// if the ball has been detected, compute desired position and call the service
		if (x_ball != 0 && y_ball != 0){
			robot_des = compute_plan();
			football_game::ReachGoal srv;
			srv.request.robot_des = robot_des;
			result = client_reach_goal.call(srv);
		}
		ros::spinOnce();
		r.sleep();
	}

	return 0;
}
