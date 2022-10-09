#!/usr/bin/env python
#The main connector script responsible for discovery and connection of the configured controllers ips/nqns
import json
import logging
import pds_logger
from systemd.journal import JournalHandler
import pds_constants
import logging.config
import os.path
import subprocess
#Add function for module creation.
#Creating service logger to log to journalctl logs
#logging.config.fileConfig('/etc/pds/pds_logging.conf')
def read_log_level(config_file):
        with open(config_file) as f:
                lines=f.readlines()
        return lines[1].split("=")[1]

logger = logging.getLogger('pds')
logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER='PDS Service'))
level=read_log_level(pds_constants.pds_config_file)
#print level
#level='logging.'+level.strip()
logger.setLevel(level.strip())
logger.info("Starting pds service")

#logger = logging.LoggerAdapter(logger, service_name)
#Create log file to log the connection info
volume_logger_format="'%(message)s'"
volume_logger=pds_logger.create_logger('pds_volume_logger',pds_constants.pds_log_file,volume_logger_format)

#open('pds_nvmeof_nqn.log','w') as volume_logger
import pds_host_operations
import pds_module_checker

#Check if connector is run via systemctl or reboot
if os.path.exists('/var/run/pds_init_done'):
    if os.path.exists('/etc/pds/pds_reconnector_running.txt'):
        logger.error("The PDS reconnector is active, failing the attempt to start PDS service via systemctl")
        exit()
    else:
        logger.info("The PDS service is being started via systemctl")
else:
    logger.info("PDS service starting after boot")
    if os.path.exists('/etc/pds/pds_reconnector_running.txt'):
        logger.info("Previous state of PDS reconnector will be cleared as PDS service is starting after a boot")
    removefile=subprocess.Popen(['rm','-f','/etc/pds/pds_reconnector_running.txt'],stdout=subprocess.PIPE)
    if removefile.wait()==0:
        logger.debug("PDS reconnector state cleared successfully")
        
    

#Read the config file and return a json object for further processing
data=pds_host_operations.pds_read_config(pds_constants.pds_config_file)
#data=pds_host_operations.pds_read_config(configuration['pds_config_file'])
cluster_dict=data

#constants=pds_host_operations.configuration
constants=pds_host_operations.pds_get_constants()
#Perform nvme module check and IO timeout check
modulecheck=pds_module_checker.check_nvme_modules_and_load()
if modulecheck!=0:
    logger.error("Possible issues loading the NVMeoF modules")
    exit()
#Check modules and nvme utility on the host
#The boolean check in configurable via pds_constants and will be run only if the customer sets the flag to 1
if constants['module_check']==1:
	mlx_module_check=pds_module_checker.check_mlx_modules_and_load()
	#print mlx_module_check
	if mlx_module_check!=0:
		logger.error("Possible issues loading mlx modules")
		exit()

	#Check if nvme utility is installed on the host
	output=pds_module_checker.check_nvme_util()
	if output!=0:
		logger.error("nvme utility may not be installed, please check the system")
		exit()
#Potentially add a check for service state thereby preventing erronous deletion of the log file
#Empty the log file before each service start
with open(pds_constants.pds_log_file,'w') as f:
	pass
#Check network connectivity, discover and connect
#Add simlutanous support for controller and nqn
for key,val in cluster_dict.items():
    #print key
    if key == 'Constants':
        continue
    for items in val:
        if items['controller_ips']:
			for controller_ip in items['controller_ips']:
				logger.info("Attempting host operations on controller IP "+controller_ip)
				ping_result=pds_host_operations.check_ping(controller_ip)
				if ping_result == 0:
					logger.info("Network check successful, initiate connection to "+str(controller_ip))
					nqn_list=pds_host_operations.discover(controller_ip)
					logger.info("nqn list received from "+controller_ip+" is "+str(nqn_list))
					if nqn_list != -1 and type(nqn_list) == list:
						for nqn in nqn_list:
							connect_op=pds_host_operations.connect_nqn(controller_ip,nqn,key)
				else:
					volume_logger.info("XXXX "+controller_ip+" nvmeX "+key)
					logger.info("Adding nvmeX tag for "+controller_ip+" from Cluster "+key)
        if items['ip_nqn_map']:
			for ip,nqn in items['ip_nqn_map'].items():
				logger.info("Performing network check on controller IP "+ip)
				ping_result=pds_host_operations.check_ping(ip)
				if ping_result == 0:
					logger.info("Network check successful, initiate connection to "+str(ip))
					nqn_list=pds_host_operations.discover(ip)
                                        logger.info("nqn list received from "+ip+" is "+str(nqn_list))
                                        if nqn_list != -1 and type(nqn_list) == list:
						flag=pds_host_operations.set_connect_flag_ip_nqn_pair(nqn,nqn_list,ip)
					pds_host_operations.connect_nqn_with_flag(flag,nqn,ip,key)
				else:
					volume_logger.info("XXXX "+ip+" nvmeX "+key)
                                        logger.info("Adding nvmeX tag for "+ip+" from Cluster "+key)

subprocess.Popen(['touch','/var/run/pds_init_done'],stdout=subprocess.PIPE)
