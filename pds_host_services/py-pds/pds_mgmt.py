#!/usr/bin/env python
import argparse
import subprocess
import pds_logger
import logging
import logging.config
from systemd.journal import JournalHandler
import pds_constants
import json
import os.path
import datetime
import pds_host_operations
import re
#fetch configuration from pds.conf via pds_host_operations
configuration=pds_host_operations.pds_get_constants()
#configuration['pds_config_file']='/etc/pds/pds.conf'
def read_log_level(config_file):
        with open(config_file) as f:
                lines=f.readlines()
        return lines[1].split("=")[1]

def create_config(filename):
    f=open(filename)
    lines=f.readlines()
    config={}
    for line in lines:
        if '=' not in line:
            print('Invalid File Format')
            exit()
        splitline=line.split('=')
        clustername=splitline[0].strip()
        clustername=clustername.capitalize()
        controllers=splitline[1].strip()
        controllers=controllers.split()
        for controller in controllers:
            if not re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',controller):
                print ("In correct IP format provided in line "+str(line))
                exit()
        config[clustername]=[{"chassis":"","controller_ips":controllers,"ip_nqn_map":{}}]
    config['Constants']=configuration
    f.close()
    return config

def update_file(config_file,loglevel,data=None):
    if data==None:
        data=pds_host_operations.pds_read_config(pds_constants.pds_config_file)
    data['Constants']=configuration
    with open(config_file,'w') as g:
        g.write('Version=3\n')
        g.write('LOGLEVEL='+loglevel+'\n')
        #g.write(json.dumps(config,indent=4,sort_keys=True))
        g.write(json.dumps(data,indent=4,sort_keys=True))
        g.write('\n')



logger = logging.getLogger('pds')
logger.addHandler(JournalHandler(SYSLOG_IDENTIFIER='PDS Service'))
level=read_log_level(pds_constants.pds_config_file)
logger.setLevel(level.strip())
#print level

#import pds_constants
volume_logger_format="'%(message)s'"
volume_logger=pds_logger.create_logger('pds_volume_logger',pds_constants.pds_log_file,volume_logger_format)

parser = argparse.ArgumentParser()
subparsers=parser.add_subparsers(dest='optype')
#subparser defined for cluster related operations
clusterops=subparsers.add_parser('cluster',help='Namespace for cluster operations such as connect, disconnect, get information')
group = clusterops.add_mutually_exclusive_group(required=True)
group.add_argument('--connect',help='connect cluster',action='store_true')
group.add_argument('--disconnect',help='disconnect cluster',action='store_true')
group.add_argument('--get',help='get cluster info',action='store_true')
group.add_argument('--log_capture',help='Get PDS log capture',action='store_true')
clusterops.add_argument('-c','--clusterlist',nargs='+', required=True,help='List of clusters to be operated upon')
clusterops.add_argument('-i','--ip', nargs='+', required=False,help='List of IPv4 address of controllers to be operated upon')
clusterops.add_argument('-l','--loglevel', required=False,help='Change log level to the user desired level',default='INFO')
clusterops.add_argument('--csv', required=False,help='Get cluster information in csv format',action='store_true')
#subparser defined for configuration related operations
configops=subparsers.add_parser('configure',help='Namespace for config operations such as update config, revert config, set log level')
group = configops.add_mutually_exclusive_group(required=True)
group.add_argument('-u','--updateconfig',help='update/expand config for pds operations',action='store_true')
group.add_argument('-r','--revertconfig',help='revert configuration to a reduced state for pds operations',action='store_true')
configops.add_argument('-l','--loglevel', required=False,help='Change log level to the user desired level')
configops.add_argument('-f','--filename',help='filename for creating or updating the pds.conf',required=False)
configops.add_argument('-a','--add_ips', nargs='+',required=False,help='Add IPs from CLI is needed')
configops.add_argument('-c','--clustername',required=False,help='Add IPs from CLI is needed')

args = parser.parse_args()
#print args
#Setting loglevel to uesr defined value, in case loglevel is not defined by user the default log level will be WARNING
if args.loglevel:
    loglevel=args.loglevel.upper()
    if loglevel not in ['DEBUG','INFO','WARNING','CRITICAL','ERROR']:
        logger.error("Invalid loglevel entered")
        print("Invalid loglevel entered")
        exit()
else:
    loglevel=""
    
if args.optype.lower()=='cluster':
    if loglevel:
        #update_file(pds_constants.pds_config_file,loglevel)
        logger.setLevel(loglevel.strip())
    clusterlist=args.clusterlist
    #op=args.operation.strip()
    iplist=args.ip
    #if op.lower()=='connect':
    if args.connect:
        logger.info('Connect request for '+str(clusterlist))
        for cluster in clusterlist:
            print("Executing NVMe Connect for cluster "+str(cluster))
            result=pds_host_operations.cluster_connect(cluster,iplist)
            if result == 0:
                print("Successfully connected to cluster "+str(cluster))
    #elif op.lower()=='disconnect':
    elif args.disconnect:
        logger.info('Disconnect request for '+str(clusterlist))
        for cluster in clusterlist:
            pds_host_operations.cluster_disconnect(cluster,iplist)
    #elif op.lower()=='get':
    
    elif args.get:
        logger.info('Get information request for '+str(clusterlist))
        #for cluster in clusterlist:
        if args.csv:
            csvname = pds_host_operations.get_cluster_info(clusterlist,args.csv)
            print("The requested information has been downloaded to " + csvname)
        else:
            pds_host_operations.get_cluster_info(clusterlist)
            print("Successfully gathered information for "+" ".join(clusterlist)+"\n\n")
    elif args.log_capture:
        logger.info("Gathering PDS file dump")
        #generate log file
        with open('pds_capture.log','w') as outfile:
            logpull=subprocess.Popen(['journalctl','-u','pds'],stdout=outfile)
            (output, err) = logpull.communicate()
            if logpull.wait() == 0:
                pass
            else:
                print("Journal log capture for PDS service failed")
                exit()
        #Create tar ball
        now=str(datetime.datetime.now()).replace(" ","-")
        now=now.replace(":","-")
        tarname='pds_tar_'+now+'.tar.gz'
        try:
            create_dump=subprocess.check_output(['tar','-czvf',tarname,'pds_capture.log',pds_constants.pds_config_file,pds_constants.pds_log_file])
        except subprocess.CalledProcessError as c_dump:
            print("PDS log capture failed with error code ",c_dump.returncode)
        else:
            subprocess.check_output(['rm','-f','pds_capture.log'])
            print("PDS log capture successful and available at "+tarname) 
    else:
        logger.info('Invalid Operation requested')
        
if args.optype.lower()=='configure':
    if loglevel:
        #update_file(pds_constants.pds_config_file,loglevel)
        #logger.setLevel(loglevel.strip())
        pass
    else:
        loglevel=pds_host_operations.pds_read_loglevel(pds_constants.pds_config_file)
        loglevel=loglevel.strip()
        if loglevel not in ['DEBUG','INFO','WARNING','CRITICAL','ERROR']:
            loglevel='INFO'
    action=0
    if args.revertconfig:
        action=1
    elif args.updateconfig:
        action=2
    if args.filename:
        filename=args.filename
        #print filename
        if os.path.exists(filename):
            pass
        else:
            print"config file does not exist or incorrect filename entered"
            exit()

    if action==1:
        if not args.filename:
            logger.error("pds_mgmt configure must include filename")
            print("pds_mgmt configure must include -f filename")
            exit()
        config=create_config(filename)
        update_file(pds_constants.pds_config_file,loglevel,config)
        logger.info('New config file created at '+str(pds_constants.pds_config_file))
        print('Successfully created PDS config file')

    if action == 2:
        config=pds_host_operations.pds_read_config(pds_constants.pds_config_file)
        if args.filename:
            data=create_config(filename)
            #Code to take care of the existing IPs in the config file and appending only the new, changed IPs to the config
            #Addition of a new cluster supported
            #If an unreachable IP is provided in the config for a new cluster, an error message will be logged in journal log
            #stating that the Cluster is invalid and no updates of nvmeX will be done to the log file.
            #The IPs in the config file can be removed by running the pds_mgmt utility configure -r option.
            #Removal should be done once the desired IP has been disconnected with the pds_mgmt utility
            for key,value in data.items():
                if key == 'Constants':
                    continue
                if key in config:
                    data_controller_list=data[key][0]['controller_ips']
                    config_controller_list=config[key][0]['controller_ips']
                    final_controller_list=list(set(data_controller_list+config_controller_list))
                    config[key][0]['controller_ips']=final_controller_list
                if key not in config:
                    data_controller_list=data[key][0]['controller_ips']
                    config[key]=[{'controller_ips':data_controller_list,"chassis":"","ip_nqn_map":{}}]
                
            update_file(pds_constants.pds_config_file,loglevel,config)
            print("Successfully updated PDS configuration")
        elif not args.filename and not args.add_ips and not args.clustername:
            update_file(pds_constants.pds_config_file,loglevel)
            print("Successfully updated PDS loglevel to " + str(loglevel))
        elif args.add_ips and args.clustername:
            clustername=args.clustername.capitalize()
            config=pds_host_operations.pds_read_config(pds_constants.pds_config_file)
            if clustername in config:
                for ip in args.add_ips:
                    if not re.search(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',ip):
                        print ("Invalid IP \""+str(ip)+"\" provided as input ")
                        exit()
                    #print "config info "+str(config)
                    if ip not in config[clustername][0]['controller_ips']:
                        config[clustername][0]['controller_ips'].append(ip)
                update_file(pds_constants.pds_config_file,loglevel,config)
                print("Successfully updated PDS configuration")
                
            else:
                print "Cluster not in pds.conf, please update pds.conf before adding IP addresses" 
        elif args.add_ips and not args.clustername:
            print("Both IP and cluster name inputs expected while updating Cluster definition only one input provided")
            exit()
        elif args.clustername and not args.add_ips:
            print("Both IP and cluster name inputs expected while updating Cluster definition only one input provided")
            exit()
        logger.info('The config file '+pds_constants.pds_config_file+' has been updated')

    
