from ecat_slave import Master  # Import the Master class from ethercat.py
import time

time.sleep(10)
master = Master()
while not master.connection_status:
    master = Master()
master.setUpSlaves()

if(master.device_count==2):
    print("GooooooooD")
else:
    print("BaaaaaaaaD")