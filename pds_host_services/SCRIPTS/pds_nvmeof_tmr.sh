#!/bin/bash
#set -x
PATH=$PATH:/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

PDS_HOME_DIRECTORY=/etc/pds
source $PDS_HOME_DIRECTORY/pds.conf
PDS_TMR_RUNNING=${PDS_HOME_DIRECTORY}/pds_nvmeof_tmr_running
PDS_NVME_FABRICS_PATH=/sys/devices/virtual/nvme-fabrics/ctl
CONTROLLER_NQN_LOG=$PDS_HOME_DIRECTORY/pds_nvmeof_nqn_list.log
PDS_TIMER_STRING="[pds nvme-of crond timer]"
transport='rdma'

PDS_DEINITIALIZE_RUNNING=${PDS_HOME_DIRECTORY}/pds_nvmeof_deinitialize_running
if [[ -f "${PDS_DEINITIALIZE_RUNNING}" ]] ; then
	echo "${PDS_TIMER_STRING} systemctl stop pds.service is running."
	exit 0
fi

if [[ -f "${PDS_TMR_RUNNING}" ]]; then
	echo "${PDS_TIMER_STRING} Exiting as an instance of pds timer is already running!"
	exit 1
else
	touch ${PDS_TMR_RUNNING}
fi

STATUS=$(systemctl is-active pds.service)
if [[ ${STATUS} == "active" ]]; then
	echo "pds.service is active" > /dev/null
else
	rm -f "${PDS_TMR_RUNNING}"
	exit 0
fi

if [[ -f "${CONTROLLER_NQN_LOG}" ]] ; then
	echo "File exists" > /dev/null
else
	rm -f "${PDS_TMR_RUNNING}"
	exit 0
fi

function is_nqn_connected()
{
	nvme_dev_name=( $(grep -nr "${1}" ${PDS_NVME_FABRICS_PATH}/*/subsysnqn  2>/dev/null | awk -F ":" '{print $1}' | awk -F "/" '{print $7}') )
	[[ -z "${nvme_dev_name}" ]] && return 1 || return 0
}

function get_device_controller_ip()
{
	controller_ip=$(grep $1 $CONTROLLER_NQN_LOG | awk '{print $2}')
	echo $controller_ip
}

function get_device_controller_nqn()
{
        controller_nqn=$(grep $1 $CONTROLLER_NQN_LOG | awk '{print $3}')
        echo $controller_nqn
}

function get_controller_ping_status()
{
	ping -c 3 -W 5 $1 > /dev/null
	if [[ $? -eq 0 ]];then
		echo 0
	else
		echo 1
	fi
			
}

function connect_previous_disconnects()
{
local arr=("$@")
for ip in ${arr[@]}
    do
        if [[ $(get_controller_ping_status $ip) == 0 ]];then
        		echo "${PDS_TIMER_STRING} The controller with IP $ip is now reachable, attempting an nvme connect"
				if [[ $cntrlr_ip_addr_list ]];then
					 total_connect_count=`nvme discover -t rdma -a ${ip} | grep subnqn | awk '{print $2}' | wc -l`
					 nqns=$(nvme discover -t rdma -a $ip | grep subnqn | awk '{print $2}' | xargs)
				 fi
				 if [[ $nqns_list && $nqns_cntrlr_ip_list ]];then
					 total_connect_count=${#nqns_list[@]}
					 nqns=${nqns_list[@]}
				 fi
				 connect_count=0
				 for nqn in ${nqns[@]}
				 do
						 $(nvme connect -t rdma -a $ip -n $nqn)
						 if [[ $? -ne 0 && $? -ne 142 ]];then
							 echo "${PDS_TIMER_STRING} Connect for $nqn with IP $ip is unsuccessful"
						 else
							 nvmelist=$(ls -d $PDS_NVME_FABRICS_PATH/nvme*)
							 echo ${nvmelist[@]}
							 #Iterate over the list of directories to compare and find the nvme device for each IP and NQN combination
							 for i in ${nvmelist[@]}
							 do
								 if [[ $nqn == $(cat $i/subsysnqn) ]];then
									 current_address=$(cat $i/address|grep -o "[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}")
									 if [[  $ip == $current_address ]];then
										 nvmedev=$(cat $i/uevent | grep DEVNAME |tr 'DEVNAME=' ' '|xargs)
										 echo "$nqn $ip $nvmedev" >> $CONTROLLER_NQN_LOG
									 fi
								 fi
							 done
						 echo "${PDS_TIMER_STRING} Connect for $nqn with IP $ip is successful"
						 connect_count=$((connect_count + 1))
						 fi
				 done
				 echo $total_connect_count
				 echo $connect_count
				 if [[ $total_connect_count == $connect_count ]];then
						 echo "${PDS_TIMER_STRING} All volumes on the IP $x have been connected, removing the XXXX string for $ip"
						 sed -i "/${ip} nvmeX/d" $CONTROLLER_NQN_LOG
				 fi
         fi
 done	
}

#Get previous disconnected IPs from the log file and try to connect via the connect_previous_disconnects function
previous_disconnects=$(cat /etc/pds/pds_nvmeof_nqn_list.log | grep "nvmeX" | awk '{print $2}'|xargs)
connect_previous_disconnects ${previous_disconnects[@]}
#Get number of connected nvme volumes from log file.
already_connected=$(cat $CONTROLLER_NQN_LOG |grep -v "nvmeX"| wc -l)
#Get actually connected nvme volumes on the system.
current_connections=$(nvme list | grep PVL | wc -l)
#Check if the log file has the same number of connections as the actual connections.
if [[ "${already_connected}" -ne "${current_connections}" ]]; then
	#Connect all missing NQNs in the cntrlr_ip_addr_list provided in the pds.conf file.
	log_devices=( $(cat $CONTROLLER_NQN_LOG |grep -v "nvmeX"| awk '{print $3}') )
	ctrlr_ips=( $(cat $CONTROLLER_NQN_LOG | awk '{print $2}') )
	ctrlr_nqns=( $(cat $CONTROLLER_NQN_LOG | awk '{print $1}') )
	for i in "${!log_devices[@]}" ; do
		if [[ -d "${PDS_NVME_FABRICS_PATH}/${log_devices[$i]}" ]]; then
			subsysnqn=$(cat ${PDS_NVME_FABRICS_PATH}/${log_devices[$i]}/subsysnqn)
			if [[ "${subsysnqn}" == "${ctrlr_nqns[$i]}" ]]; then
				address=$(cat ${PDS_NVME_FABRICS_PATH}/${log_devices[$i]}/address | awk -F "," '{print $1}' | awk -F "=" '{print $2}')
				if [[ "${address}" == "${ctrlr_ips[$i]}" ]]; then
					continue
				fi
			fi
		fi
		echo "${PDS_TIMER_STRING} Trying to connect NQN ${ctrlr_nqns[$i]} at ${ctrlr_ips[$i]}..."
		$(nvme connect -t ${transport} -a ${ctrlr_ips[$i]} -n ${ctrlr_nqns[$i]} -i ${num_io_queue})
		if [[ $? -ne 0 ]]; then
			echo "<1>${PDS_TIMER_STRING} Failed to connect NQN ${ctrlr_nqns[$i]} at ${ctrlr_ips[$i]}!"
		else
			BREAKWHILE=false
			while true; do
				nvme_devices=( $(grep -rl "${ctrlr_nqns[$i]}" ${PDS_NVME_FABRICS_PATH}/*/subsysnqn 2>/dev/null | awk -F "/" '{print $7}') )
				for connected_nvme_device in ${nvme_devices[@]} ; do
					conn_ctrlr_ip=$(cat ${PDS_NVME_FABRICS_PATH}/${connected_nvme_device}/address | awk -F "," '{print $1}' | awk -F "=" '{print $2}')
					if [[ "${conn_ctrlr_ip}" == "${ctrlr_ips[$i]}" ]] ; then
						line=$(($i + 1))
						sed -i "${line}s/${log_devices[$i]}/${connected_nvme_device}/" /etc/pds/pds_nvmeof_nqn_list.log
						BREAKWHILE=true
						break
					fi
				done
				if $BREAKWHILE ; then
					break
				fi
				sleep 1
			done
		fi
	done
fi

rm -f "${PDS_TMR_RUNNING}"
