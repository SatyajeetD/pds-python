#!/usr/bin/env python
import subprocess
import pds_logger
import logging
import pds_constants
from systemd.journal import JournalHandler
import os.path

def read_log_level(config_file):
        with open(config_file) as f:
                lines=f.readlines()
        return lines[1].split("=")[1]

#configuration=pds_constants.pds_get_constants()

#logging.config.fileConfig('/etc/pds/pds_logging.conf')
logger = logging.getLogger('pds')
logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER='PDS Service'))
level=read_log_level(pds_constants.pds_config_file)
logger.setLevel(level.strip())

import pds_host_operations
if os.path.exists('/var/run/pds_init_done'):
    if os.path.exists('/etc/pds/pds_reconnector_running.txt'):
        logger.error("The PDS reconnector is active, failing the attempt to stop PDS service via systemctl")
        exit()

with open(pds_constants.pds_log_file,'r') as f:
       for line in f.readlines():
		flag=0
		if 'nvmeX' not in line:
			nvmedev=line.split()[-2]
			disconnect=pds_host_operations.disconnect(nvmedev)
			logger.info(" disconnect value for "+nvmedev+" is "+str(disconnect),extra={'service_name':'PDS Service'})
			if disconnect == 0:
				logger.info("Disconnecting "+nvmedev+" successful!",extra={'service_name':'PDS Service'})
			else:
				logger.info("Error disconnecting "+nvmedev)
				flag=1

#Clear file contents after disconnection if all disconnects are successful
try:
	if flag ==0:
		with open(pds_constants.pds_log_file,'w') as f:
			pass
except:
	logger.error("The pds_nvmeof_nqn.log file is already empty, nothing to disconnect")
