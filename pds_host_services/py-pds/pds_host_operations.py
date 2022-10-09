#Host function library to perform host functions such as nvme discover, connect, disconnect etc
import os
import shutil
import subprocess
import logging
import re
import json
import pds_constants
import csv
import datetime
import time
hostlogger=logging.getLogger('pds.host')
hostlogger.info('pds_host_logger_initialized')
volume_logger=logging.getLogger('pds_volume_logger.host')
failed_connect=[]
import traceback
import syslog

def pds_read_config(config_file):
    data={}
    with open(config_file) as f:
        lines=f.readlines()
        if 'Version=3' not in lines[0]:
            pass
        else:
            lines=lines[2:]
            config_str=""
            for line in lines:
                config_str+=line
            data=json.loads(config_str)
    return data

def pds_get_constants():
    constants={}
    data=pds_read_config(pds_constants.pds_config_file)
    if data:
        constants=data["Constants"]
    else:
        try:
            with open('/etc/pds/pds.conf') as f:
                lines=f.readlines()
                for line in lines:
                    if 'num_io_queue' in line:
                        line=line.split('=')
                        num_io_queues=line[1].strip()
            constants={"protocol":"rdma","connection_port":4420,"module_check":0,"num_queues":num_io_queues,"io_timeout":600}
        except:
            constants={"protocol":"rdma","connection_port":4420,"module_check":0,"num_queues":4,"io_timeout":600}
            
    return constants

def pds_read_loglevel(config_file):
    with open(config_file) as f:
        lines=f.readlines()
    loglevel=lines[1].split('=')[1].strip()
    return loglevel
#Read constants from the config file and create a dictionary of values
#configuration=pds_get_constants()

def get_nvme_util_location():
    nvme=subprocess.Popen(['/usr/bin/which','nvme'],stdout=subprocess.PIPE)
    location=nvme.communicate()[0]
    hostlogger.info("RETURNING NVMEUTIL AS "+str(location))
    return location.strip()
def syslog_trace(trace):
    '''Log a python stack trace to syslog'''

    log_lines = trace.split('\n')
    for line in log_lines:
        if len(line):
            syslog.syslog(line)

def update_devicename_log_file(devicenameinfile,ip,nqn,nvmedevicename):
    shutil.copy(pds_constants.pds_log_file,'/etc/pds/reconnect_temp_file')
    with open('/etc/pds/reconnect_temp_file') as g:
        lines=g.readlines()
    with open('/etc/pds/reconnect_temp_file','w') as g:
        for line in lines:
            if devicenameinfile == line.split()[2].strip() and ip == line.split()[1].strip() and nqn == line.split()[0][1:].strip():
                hostlogger.info("Removing the old devicename i.e "+str(devicenameinfile))
                pass
            elif nvmedevicename == line.split()[2].strip() and ip != line.split()[1].strip():
                hostlogger.info("Marking the device that was originally "+str(nvmedevicename)+" to nvmeX")
                line=line.split('\t')
                line[2]='nvmeX'
                line="\t".join(line)
                g.write(line)
            else:
                g.write(line)
    shutil.copy('/etc/pds/reconnect_temp_file',pds_constants.pds_log_file)

def checknvmedevname(ip,nqn,nvmedevicename):
    updatedevicename=0
    with open(pds_constants.pds_log_file) as f:
        lines=f.readlines()
    for line in lines:
        if ip == line.split()[1] and nqn==line.split()[0][1:]:
            devicenameinfile=line.split()[2].strip()
            if devicenameinfile != nvmedevicename:
                hostlogger.info("Device name for nvme device with NQN:"+str(nqn)+" and IP:"+str(ip)+" has been changed")
                update_devicename_log_file(devicenameinfile,ip,nqn,nvmedevicename)
                updatedevicename=1
    return updatedevicename
    
            
def connect_nqn(controller,nqn,key,reconnect=0):
    configuration=pds_get_constants()
    #Fetching protocol, queue nums, port from constants
    cmd="/usr/sbin/nvme connect -t "+configuration['protocol']+" -a "+controller+" -s "+str(configuration['connection_port'])+" -n "+nqn+" -i "+str(configuration['num_queues'])
    connect=subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    time.sleep(1)
    nvmedevicename=getnvme(controller,nqn)
        
    if connect.wait() == 0:
        #nvmedevicename=getnvme(controller,nqn)
        hostlogger.info("Connection to "+nqn+" successful at ip "+controller)
        updatedevicename=checknvmedevname(controller,nqn,nvmedevicename)
        if reconnect==0:
            hostlogger.info("Adding log "+str(nqn)+"\t"+str(controller)+"\t"+str(nvmedevicename)+"\t"+str(key)+" to "+pds_constants.pds_log_file)
            volume_logger.info(str(nqn)+"\t"+str(controller)+"\t"+str(nvmedevicename)+"\t"+str(key))
        else:
            if updatedevicename == 1:
                hostlogger.info("Updating PDS log file with latest information")
                volume_logger.info(str(nqn)+"\t"+str(controller)+"\t"+str(nvmedevicename)+"\t"+str(key))
            else:
                hostlogger.info("Not logging to the log file as reconnect value for new connection is non-zero and device name has not been updated")
    elif connect.wait() == 142:
        #nvmedevicename=getnvme(controller,nqn)
        hostlogger.info("Volume "+nqn+" already connected via ip "+controller)
        if reconnect==0:
            hostlogger.info("Adding log "+nqn+"\t"+controller+"\t"+nvmedevicename+"\t"+key+" to "+pds_constants.pds_log_file)
            volume_logger.info(str(nqn)+"\t"+str(controller)+"\t"+str(nvmedevicename)+"\t"+str(key))
        else:
            hostlogger.info("Not logging to the log file as reconnect value for existing connection is non-zero")
    else:
        hostlogger.info("Error connecting to "+nqn+" via "+controller+" from cluster "+key)
        return -1
    return 0



def getnvme(controller,nqn):
    nvmelist=[]
    ip_pattern=re.compile("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
    x=subprocess.check_output(['ls','/sys/devices/virtual/nvme-fabrics/ctl/'])
    x=x.split('\n')[:-1]
    for device in x:
        if 'nvme' in device:
            nvmelist.append(device)
    for nvme in nvmelist:
            subnqn_process=subprocess.Popen(["cat","/sys/devices/virtual/nvme-fabrics/ctl/"+nvme+"/subsysnqn"],stdout=subprocess.PIPE)
            subnqn=subnqn_process.communicate()[0].rstrip()
            ip_process=subprocess.Popen(["cat","/sys/devices/virtual/nvme-fabrics/ctl/"+nvme+"/address"],stdout=subprocess.PIPE)
            ip=ip_process.communicate()[0]
            ip=ip_pattern.findall(ip)[0]
            if controller == ip and nqn == subnqn:
                    return nvme
    
def discover(controller):
    try:
        nqn_list=[]
        hostlogger.info("Executing discover for the controller "+str(controller))
        #For subprocess to work correctly the full path as shown below is needed for any executable
        cmd=["/usr/sbin/nvme", "discover", "-t", "rdma", "-a" ,str(controller)]
        ps1=subprocess.Popen(cmd,stdout=subprocess.PIPE)
        discover_status=ps1.wait()
        if discover_status == 0:
            hostlogger.info("discover command successful for "+str(controller))
            ps2=subprocess.Popen(['grep','subnqn'],stdin=ps1.stdout,stdout=subprocess.PIPE)
            ps3=subprocess.Popen(['awk','{print $2}'],stdin=ps2.stdout,stdout=subprocess.PIPE)
            nqn_list=ps3.communicate()[0]
            nqn_list=nqn_list.rstrip()
            nqn_list=nqn_list.split('\n')
            return nqn_list
        else:
            hostlogger.info("NVMe discovery process encountered an error with status "+str(discover_status))
            return -1
    except:
        syslog_trace(traceback.format_exc())
    
def disconnect(nvmedev):
    
    disconnect=subprocess.Popen(['nvme','disconnect','-d',nvmedev],stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if disconnect.wait() == 0:
        hostlogger.info('Disconnect successful for device '+str(nvmedev))
        return 0
    else:
        return -1

#Change name to check_connectivity
def check_ping(controller_ip):
    ping_process=subprocess.Popen(["ping","-c","3",controller_ip],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    ping_result=ping_process.wait()
    if ping_result==0:
        hostlogger.info("Network check successful for IP "+str(controller_ip))
        return 0
    else:
        hostlogger.error("ping to "+controller_ip+" is not successful,check network connecitivity")
        return -1

def get_nvme_device_list():
        base_path="/sys/devices/virtual/nvme-fabrics/ctl/"
        p1=subprocess.Popen(["ls",base_path],stdout=subprocess.PIPE)
        p2=subprocess.Popen(["grep","nvme"],stdin=p1.stdout,stdout=subprocess.PIPE)
        nvmenames=p2.communicate()[0].rstrip().split("\n")
        return nvmenames

def get_nvme_device_name(controller_ip,nqn,nvme_device_list):
        base_path="/sys/devices/virtual/nvme-fabrics/ctl/"
        ip_pattern=re.compile("\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        for nvme in nvme_device_list:
                subnqn_process=subprocess.Popen(["cat",base_path+nvme+"/subsysnqn"],stdout=subprocess.PIPE)
                subnqn=subnqn_process.communicate()[0].rstrip()
                #print subnqn
                ip_process=subprocess.Popen(["cat",base_path+nvme+"/address"],stdout=subprocess.PIPE)
                ip=ip_process.communicate()[0]
                #print "ip is",ip
                ip=ip_pattern.findall(ip)[0]
        #print ip

                if controller_ip == ip and nqn == subnqn:
                        return nvme
        return -1

def check_connection_state(nvmedevice,nqn):
    base_path=pds_constants.default_nvme_path+nvmedevice+"/state"
    #state=subprocess.Popen(['cat',base_path],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        state=subprocess.check_output(['cat',base_path],stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        return "File Missing"
    if state.strip() == 'live':
        subsysnqn=subprocess.check_output(['cat',pds_constants.default_nvme_path+nvmedevice+"/subsysnqn"])
        subsysnqn=subsysnqn.strip()
        if subsysnqn != nqn:
            state='Altered'
    return state

def get_nvme_device_map_from_file():
    details=[]
    nvmedevicemap={}
    with open(pds_constants.pds_log_file,'r') as f:
        for line in f.readlines():
            details=line.split()
            nvmedevicemap[details[2]]=[details[0],details[1]]
    with open('/etc/pds/pds_nvmeof_nqn_cluster_temp.log','w') as f:
        pass
    g=open('/etc/pds/pds_nvmeof_nqn_cluster_temp.log','a')
    with open(pds_constants.pds_log_file,'r') as f:
        lines=f.readlines()
        for line in lines:
            if cluster in line:
                pass
            else:
                g.write(line)
    g.close()
    shutil.copy('/etc/pds/pds_nvmeof_nqn_cluster_temp.log','/etc/pds/pds_nvmeof_nqn.log')

def edit_log_file(controller):
    #Emtpy contents of the temp file from previous runs
    with open(pds_constants.pds_temp_log_file,'w') as f:
        pass
    g=open(pds_constants.pds_temp_log_file,'a')
    with open(pds_constants.pds_log_file,'r') as f:
        lines=f.readlines()
        for line in lines:
            if 'nvmeX' in line and controller in line:
                hostlogger.info("Removing nvmeX tag from "+controller+" as the nvme connections have been restored")
                pass
            elif 'nvmeX' in line and controller not in line:
                #print "Writing line for nvmeX for a different IP"
                g.write(line)
            else:
                g.write(line)
    g.close()
    shutil.copy(pds_constants.pds_temp_log_file,pds_constants.pds_log_file)
    #Remove temp file after operations
    cmd='rm -f '+pds_constants.pds_temp_log_file
    delete_temp_file=subprocess.Popen(cmd,shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if delete_temp_file.wait()==0:
        hostlogger.debug('The temporary log file has been deleted')

def edit_log_file_disconnect(cluster):

    with open('/etc/pds/pds_nvmeof_nqn_cluster_temp.log','w') as f:
        pass
    g=open('/etc/pds/pds_nvmeof_nqn_cluster_temp.log','a')
    with open(pds_constants.pds_log_file,'r') as f:
        lines=f.readlines()
        for line in lines:
            if cluster in line:
                pass
            else:
                g.write(line)
    g.close()
    shutil.copy('/etc/pds/pds_nvmeof_nqn_cluster_temp.log','/etc/pds/pds_nvmeof_nqn.log')

'''
def pds_read_config(config_file):
    with open(config_file) as f:
        lines=f.readlines()[2:]
        config_str=""
        for line in lines:
            config_str+=line
    data=json.loads(config_str)
    return data

def pds_get_constants():
    constants={}
    data=pds_read_config(pds_constants.pds_config_file)
    constants=data["Constants"]
    return constants
'''
def set_connect_flag_controller(key,controller_ip):
    with open(pds_constants.pds_log_file) as f:
        lines=f.readlines()
    flag=0
    if len(lines) == 0:
        hostlogger.info("Returning 0 as lines is empty")
        return 0
    for line in lines:
        if controller_ip not in line:
            pass
        #if key in line and controller_ip not in line:
                #   return 0
                #if key in line and 'nvmeX' not in line:
        #if key in line and controller_ip in line:
        if controller_ip in line:
            flag=1
            #return 1
        #if key in line and 'nvmeX' in line:
        if controller_ip in line and 'nvmeX' in line:
            flag=2
            #return 2
    return flag

def connect_controller_with_flag(flag,nqn_list,controller_ip,key):
    hostlogger.info("flag value passed is "+str(flag))
    result=0
    if flag==0:
            hostlogger.info('Clustername '+key+' not in log file, executing without reconnect flag')
            for nqn in nqn_list:
                    connect_op=connect_nqn(controller_ip,nqn,key)
                    if connect_op != 0:
                        result=1
                        return result
            return result
    elif flag==1:
            hostlogger.info('Clutername '+key+' already in logfile, executing with reconnect flag')
            for nqn in nqn_list:
                    #Avoid duplication of entries in log file
                    connect_op=connect_nqn(controller_ip,nqn,key,1)
                    if connect_op != 0:
                        result=1
                        return result
            return result
    elif flag==2:
            hostlogger.info('Clutername '+key+' in logfile with tag nvmeX, executing without reconnect flag')
            for nqn in nqn_list:
                    hostlogger.info("Running connect for "+key+" on nqn "+nqn)
                    connect_op=connect_nqn(controller_ip,nqn,key)
                    hostlogger.info("Value of "+str(connect_op))
                    if connect_op != 0:
                        result=1
                        return result
            cmd='sed -i "/nvmeX '+key+'/d" '+pds_constants.pds_log_file
            with open(pds_constants.pds_log_file,'r+') as f:
                    subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            hostlogger.info("Record for "+key+" having tag nvmeX has been removed from the log file "+str(pds_constants.pds_log_file))
            return result

def set_connect_flag_ip_nqn_pair(nqn,nqn_list,ip):
    flag=0
    for n in nqn:
        if n not in nqn_list:
            flag=1
            hostlogger.error(str(n)+' is not found in the discovered NQNs on '+ip+' please check config')
            break
    return flag

def connect_nqn_with_flag(flag,nqn,ip,key):
        if flag==0:
                for n in nqn:
                        hostlogger.info('Attempting connect on '+str(n))
                        connect_op=connect_nqn(ip,n,key)
        #else:
                #hostlogger.error('Could not connect to the NQN '+n+' please check the config file')
                #exit()

'''
def old_cluster_disconnect(cluster_list,iplist=None):
    print("In the func")
    print(iplist)
    with open(pds_constants.pds_log_file,'r') as f:
        lines=f.readlines()
    with open(pds_constants.pds_log_file,'w') as f:
            for line in lines:
                    cluster=line.split()[3][:-1]
            controller_ip=line.split()[1]

            print line
                    if 'nvmeX' not in line:
                if iplist != None:
                                if cluster in cluster_list and controller_ip in iplist:
                        nvmedev=line.split()[-2]
                        print("Disconnecting from iplist")
                        dis=disconnect(nvmedev)
                        if dis == 0:
                            hostlogger.info("Disconnecting "+nvmedev+" successful!")
                            hostlogger.info("Record for "+nvmedev+" has been removed from the log file " +str(pds_constants.pds_log_file))
                        else:
                            hostlogger.error("Error disconnecting "+nvmedev)
                    else:
                        f.write(line)
                elif iplist==None and cluster in cluster_list:
                    if cluster in cluster_list:
                        nvmedev=line.split()[-2]
                        print("Disconnecting from iplist")
                        dis=disconnect(nvmedev)
                        if dis == 0:
                            hostlogger.info("Disconnecting "+nvmedev+" successful!")
                            #hostlogger.info("Record for "+nvmedev+" has been removed from the log file " +str(configuration['pds_log_file']))
                        else:
                            hostlogger.error("Error disconnecting "+nvmedev)
                    else:
                        f.write(line)
                else:
                    f.write(line)
                    hostlogger.debug("wrote line to file "+line)
                    print("wrote line to file "+line)
            if 'nvmeX' in line:
                if iplist != None:
                    if cluster in cluster_list and controller_ip in iplist:
                        #cmd='sed -i "/'+cluster+'/d" '+pds_constants.pds_log_file
                        #hostlogger.info("Record for "+cluster+" and "+controller_ip+" having tag nvmeX has been removed from the log file "+str(configuration['pds_log_file']))
                        #subprocess.Popen(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                    else:
                        f.write(line)
                elif iplist==None:
                    if cluster in cluster_list:
                        #hostlogger.info("Record for "+cluster+" having tag nvmeX has been removed from the log file "+str(configuration['pds_log_file']))
                else:
                    f.write(line)

'''
def cluster_connect(cluster,iplist=None):
    data=pds_read_config(pds_constants.pds_config_file)
    cluster=cluster.capitalize()
    if cluster not in data:
        hostlogger.error(str(cluster)+' invalid')
        print("Cluster "+str(cluster)+" does not exist")
        exit()
    controller_list=data[cluster][0]['controller_ips']
    if iplist != None:
        for ip in iplist:
            if ip not in controller_list:
                print(str(ip) + " not configured for " + str(cluster) + ", hence will be ignored for nvme connection")
        controller_list=[controller for controller in controller_list if controller in iplist]
    
    for controller in controller_list:
        ping_result=check_ping(controller)
        if ping_result==0:
            hostlogger.info("Initiate connection to "+str(controller))
            nqn_list=discover(controller)
            hostlogger.info("NQN list available for connection "+str(nqn_list))
            if nqn_list != -1 and type(nqn_list) == list:
                hostlogger.info("NVMeoF connection in initiated on "+str(controller)+str(nqn_list))
                #with open(pds_constants.pds_log_file) as f:
                flag=set_connect_flag_controller(cluster,controller)
                hostlogger.debug("flag value returned"+str(flag))
                result=connect_controller_with_flag(flag,nqn_list,controller,cluster)
                if result == 0:
                    print("Successfully connected controller "+str(controller)+" in cluster "+str(cluster))
                else:
                    print("Failed to connect controller "+str(controller)+" in cluster "+str(cluster))

def cluster_disconnect(cluster,iplist=None):
    with open(pds_constants.pds_log_file,'r') as f:
            lines=f.readlines()
    cluster=cluster.capitalize()
    cluster_lines=[line for line in lines if cluster in line]
    if iplist != None:
        disconnect_list=[line for line in cluster_lines if line.split()[1] in iplist]
    else:
        disconnect_list=cluster_lines
    if len(disconnect_list)==0:
        print("Failed to disconnect as no devices found in "+str(cluster))
        exit()
    device_list=[line.split()[2] for line in disconnect_list if disconnect(line.split()[2])==0]
    if len(device_list)==0:
        device_list.append(-1) 
    if -1 not in device_list:
        print("Successfully disconnected devices from "+str(cluster)+"\n"+"\n".join(device_list))
    else:
        print("Failed to disconnect one or more devices for "+str(cluster))
    with open(pds_constants.pds_log_file,'w') as f:
        for line in lines:
            if line.split()[2] in device_list or ('nvmeX' in line and cluster in line and line.split()[1] in iplist):
                pass
            else:
                f.write(line)
#   device_list=[]
#   for d in disconnect_list:
#       nvmedevice=d.split()[2]
#       disconnect_status=disconnect(nvmedevice)
#       if disconnect_status == 0:
#           hostlogger.info("Disconnecting "+nvmedevice+" successful!")
#           device_list.append(nvmedevice)
#           hostlogger.info("Record for "+nvmedevice+" has been removed from the log file " +str(pds_constants.pds_log_file))
#       else:
#           hostlogger.error("Error disconnecting "+nvmedevice)
        
def change_log_level(loglevel):
    
    flag=0
    with open('/etc/pds/pds_logging.conf') as f:
        lines=f.readlines()
    with open('/etc/pds/pds_logging.conf','w') as f:
        pass
    with open('/etc/pds/pds_logging.conf','a') as f:

        for line in lines:
            if flag==0:
                f.write(line)
                if 'logger_pds' in line:
                    flag=1
            elif flag==1:
                print line
                line='level='+str(loglevel)
                print line
                f.write('level='+str(loglevel)+'\n')
                flag=0  

def read_log_level(config_file):
    with open(config_file) as f:
        lines=f.readlines()
    return lines[1].split("=")[1]
    

def get_cluster_info(clusterlist,csvoption=0):
    cluster_all=0
    with open(pds_constants.pds_log_file) as f:
        lines=f.readlines()
    if len(clusterlist) == 1 and clusterlist[0].lower() == 'all':
        cluster_all=1
    if csvoption:
        header=['NQN','IP','DEVICENAME','CLUSTERNAME']
        csvname='pds_cluster_csv_'+str(datetime.datetime.now())+'.csv'
        with open(csvname, 'w') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            if cluster_all == 1:
                for line in lines:
                    writer.writerow(line.split())
            else:
                for cluster in clusterlist:
                    cluster=cluster.capitalize()
                    for line in lines:
                        if cluster.strip() == line.split()[3].strip("'"):
                            writer.writerow(line.split())
        return csvname
    else:
        flag=0
        for cluster in clusterlist:
            cluster=cluster.capitalize()
            print 20*"#"+str(cluster)+20*"#"
            print("NQN\tIP\tDEVICENAME\tCLUSTERNAME")
            if cluster_all == 1:
                for line in lines:
                    print (line)
            else:
                for line in lines:
                    if cluster.strip()==line.split()[3].strip("'"):
                        print line
                        flag=1
                if flag==0:
                    print "Cluster "+str(cluster)+" not found"
            print 46*"#"

