#/usr/bin/python

import math
import glob
import random
import os
import shutil


def computeLatLong(x, y, z):

    app = math.sqrt(math.pow(x, 2.0) + math.pow(y, 2.0))
    log = math.atan2(z, app)
    lat = math.atan2(y, x)

    return [lat, log]


def fromQuaterniontoHTCVive(qx, qy, qz, qw):
	
	x = 2*qx*qz + 2*qy*qw
	y = 2*qy*qz - 2*qx*qw
	z = 1 - 2*math.pow(qx,2) - 2*math.pow(qy,2)
	
	return [x, y, z]
	

def parseViewport(viewport, video):

	f = open("tmp_%s.txt" % video, "w+")

	#First line contains instructions
	viewport.readline()
	elapsed_time = 0.0
	time_previous = 0.0
	start_log = True

	for line in viewport:
		
		time = float(line.split(",")[1])
		#Avoid using the first entries of the dataset (due to headset initialization, readings could be wrong)
		if (not start_log or time < 0.1):

			elapsed_time += (time - time_previous)*1000
			
			#Sampling rate is about 20 ms
			if (elapsed_time >= 20.0):

				#The authors of the dataset follow the quaternion convention to express coordinates on a 3D sphere (more info on dataset website and associated paper)
				qx = float(line.split(",")[2])
				qy = float(line.split(",")[3])
				qz = float(line.split(",")[4])
				qw = float(line.split(",")[5])

				#This function translates the quaternion coordinates into classical x-y-z coordinates for the HTV Vive
				[hmd_x, hmd_y, hmd_z] = fromQuaterniontoHTCVive(qx, qy, qz, qw)

				#Translate the x-y-z coordinates for HTV Vive into x-y-z coordinates for Gear VR (Note: I consider Gear VR as default headset)
				[gvr_x, gvr_y, gvr_z] = [hmd_x, hmd_y, -hmd_z]

				#Translate x-y-z coordinates for Gear VR into latitude and longitude on the equirectangular projection (i.e., classical x-y coordinates in a 2D system).
				#The y and z coordinates need to be switched (this depends on the way Gear VR 3D coordinates are expressed)
				[x, y] = computeLatLong(gvr_x, gvr_z, gvr_y)

				f.write("%f;%f,%f\n" % (elapsed_time, x, y))
			
				elapsed_time = 0.0

			time_previous = time
			start_log = False

	f.close()			


if __name__ == "__main__":

	#Name of the videos (dataset: https://wuchlei-thu.github.io/)
	videos = ["video_0", "video_1", "video_2", "video_3", "video_4", "video_5", "video_6", "video_7", "video_8"]
	#Number of users involved in the test
	num_users = 48

	#Folder with raw viewport traces
	raw_viewport = "./raw_viewports/"
	#Output folders (group processed viewports per video and per user)
	per_video = "./per_video_roberto/"
	per_user = "./per_user_roberto/"

	if os.path.exists("%s" % per_video):
		shutil.rmtree(per_video)
	if os.path.exists("%s" % per_user):
		shutil.rmtree(per_user)

	vw_id = {}
	for v in videos:
		if not os.path.exists("%s/%s" % (per_video, v)):
    			os.makedirs("%s/%s" % (per_video, v))
		vw_id[v] = 0

	for user_id in range(0, num_users):
		
		if not os.path.exists("%s/user_%i" % (per_user, user_id)):
    			os.makedirs("%s/user_%i" % (per_user, user_id))

		for v in videos:

			#Raw viewport for specific video/user
			vw = "%s/%i/%s.csv" % (raw_viewport, user_id+1, v)

			f_vw = open(vw, "r")
			parseViewport(f_vw, v)
			f_vw.close()

			if os.path.exists("tmp_%s.txt" % v):
				shutil.copyfile("tmp_%s.txt" % v, "%s/%s/viewport_it%i.txt" % (per_video, v, vw_id[v]))
				shutil.copyfile("tmp_%s.txt" % v, "%s/user_%i/%s.txt" % (per_user, user_id, v))
				os.remove("tmp_%s.txt" % v)
				vw_id[v] += 1
