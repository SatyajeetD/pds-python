#!/usr/bin/env python
import re
import subprocess
import pds_logger
from systemd.journal import JournalHandler
import pds_constants
import logging
import logging.config
from os.path import exists

def read_log_level(config_file):
        with open(config_file) as f:
                lines=f.readlines()
        return lines[1].split("=")[1]

#configuration=pds_constants.pds_get_constants()
#Create logger object for reconnector to log to journalctl
#logging.config.fileConfig('/etc/pds/pds_logging.conf')
logger = logging.getLogger('pds')
logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER='PDS Service'))
level=read_log_level(pds_constants.pds_config_file)
logger.setLevel(level.strip())
logger.info("Running PDS reconnector")

volume_logger_format="'%(message)s'"
volume_logger=pds_logger.create_logger('pds_volume_logger',pds_constants.pds_log_file,volume_logger_format)

import pds_host_operations
import pds_module_checker

def create_reconnector_file():
    cmd=['touch','/etc/pds/pds_reconnector_running.txt']
    r=subprocess.Popen(cmd,stdout=subprocess.PIPE)
    result=r.wait()
    if result == 0:
        logger.debug("Created pds running file")

def remove_reconnector_file():
    cmd=['rm','-f','/etc/pds/pds_reconnector_running.txt']
    r=subprocess.Popen(cmd,stdout=subprocess.PIPE)
    result=r.wait()
    if result == 0:
        logger.debug("pds running file removed")
def check_reconnector_file():
    if exists('/etc/pds/pds_reconnector_running.txt'):
        logger.error("Another instance of PDS reconnector in progress, not starting reconnector")
        exit()
    
    
def check_pds_status():
    cmd=cmd=["systemctl","status","pds.service"]
    r=subprocess.Popen(cmd,stdout=subprocess.PIPE)
    result=r.wait()
    if result == 0:
        logger.info("PDS service is in running state, continuing reconnector execution")
    else:
        logger.error("PDS service is not running, exiting reconnector")
        exit()

check_pds_status()
check_reconnector_file()
create_reconnector_file()

with open(pds_constants.pds_log_file,'r')as f:
    lines=f.readlines()
#The below code is to find the lowest nvme device number in pds log file
#The reconnect sequence will then follow the lowest to highest numbering in the log file
#This will prevent the device numbers from changing if the log file has unsorted device numbers which may happen 
#As with pds_mgmt the user can disconnect and reconnect any cluster at any time.

newlines=[]
nvmeXlines=[]
for line in lines:
    if 'nvmeX' not in line:
        newlines.append(line.split()[2][4:])
#    else:
#        nvmeXlines.append(line)
newlines=list(map(int,newlines))
newlines.sort()
newlines=['nvme'+str(x) for x in newlines]
unreachable_ips=[]
index=0
if newlines:
    for line in lines:
        if newlines[0] in line:
            break
        else:
            index+=1
lines=lines[index:]+lines[:index]
lines=lines+nvmeXlines
#After finding the sequence for reconnection below code is executing actual reconnects
processed_ips=[]
nvmex_unreachable_ip=[]
#processed_ips list will be used in the else block of the below loop to keep track of which IPs have already been processed.
#This is useful in case the log file has more than 1 nvmeX tags with the same IP.
for line in lines:
    line=line.split()
    nqn=line[0][1:]
    controller=line[1]
    device=line[2]
    cluster=line[3][:-1]
            
    #The if condition checks the state for nvme devices that are in the log file but may not have their state=live
    if device != 'nvmeX':
        logger.info("Checking state for device "+str(device))
        state=pds_host_operations.check_connection_state(device,nqn)
        if state.strip() == "File Missing":
            logger.error("The /sys entry for "+device+" is missing via the "+controller)
        if state.strip() != 'live':
            if controller not in unreachable_ips:
                ping_status=pds_host_operations.check_ping(controller)
                if ping_status == 0:
                    discover_list=pds_host_operations.discover(controller)
                    if discover_list != -1 and type(discover_list) == list:
                        if nqn in discover_list:
                            connect_op=pds_host_operations.connect_nqn(controller,nqn,cluster,1)
                else:
                    unreachable_ips.append(controller)
                    logger.error("Cannot reach "+controller+" for "+nqn+", it will be retried in the next cycle")
        else:
            logger.info("Connection state for "+device+" with nqn="+nqn+" and controller IP="+controller+" is live")
    #The else condition checks for any IP that was unreachable earlier and hence has an nvmeX tag for it.
    else:
        if controller in processed_ips:
            continue
        else:
            logger.debug("processing nvmeX tag for IP "+str(controller))
            if controller not in nvmex_unreachable_ip:
                ping_status=pds_host_operations.check_ping(controller)
                if ping_status == 0:
                    logger.info("Previously unreachable IP "+str(controller)+" now live")
                        
                    discover_list=pds_host_operations.discover(controller)
                    if discover_list != -1 and type(discover_list) == list:
                        logger.debug("Discover list is: "+str(discover_list))
                        data=pds_host_operations.pds_read_config(pds_constants.pds_config_file)
                        cluster_dict=data
                        #print cluster_dict
                        for items in cluster_dict[cluster]:
                            if controller in items["controller_ips"]:
                                #print discover_list
                                for nqn in discover_list:
                                    connect_op=pds_host_operations.connect_nqn(controller,nqn,cluster)
                            elif controller in items["ip_nqn_map"]:
                                for nqn in items["ip_nqn_map"][controller]:
                                    connect_op=pds_host_operations.connect_nqn(controller,nqn,cluster)
                                    
                        #Edit log file to remove the nvmeX tags
                        pds_host_operations.edit_log_file(controller)
                        processed_ips.append(controller)
                else:
                        logger.error("IP "+str(controller)+" unreachable further ops on this IP will be skipped for this run")
                        nvmex_unreachable_ip.append(controller)
remove_reconnector_file()   
