#!/bin/bash

source /etc/pds/pds.conf

trap cleanup SIGHUP SIGINT SIGTERM 15 2

kernel_version=`uname -r | tr "." " " | awk '{print $1}'`
kernel=`uname -r`
pds_need_network_restart=false

transport='rdma'
SLEEP_ON_CONNECT=true
SLEEP_TIME=1
PDS_NVME_FABRICS_PATH=/sys/devices/virtual/nvme-fabrics/ctl

PDS_STRING="[pds nvme-of service]"

PDS_HOME_DIR=/etc/pds
CONTROLLER_NQN_LOG=${PDS_HOME_DIR}/pds_nvmeof_nqn_list.log
PDS_DEINITIALIZE_RUNNING=${PDS_HOME_DIR}/pds_nvmeof_deinitialize_running
PDS_TMR_RUNNING=${PDS_HOME_DIR}/pds_nvmeof_tmr_running
PDS_INIT_DONE=/var/run/pds_init_done

cleanup()
{
	touch "${PDS_DEINITIALIZE_RUNNING}"
	for (( i = 0 ; i < 3 ; i++ )); do
		pds_vol_nqns=$(cat ${CONTROLLER_NQN_LOG} | awk '{print $1}' | sort | uniq)

		#Check if any PVL device is connected. If not then return.
		connected_pvl_devices_count=$(nvme list | grep -c PVL)
		if [[ ${connected_pvl_devices_count} -eq 0 ]]; then
			rm -f "${CONTROLLER_NQN_LOG}"
			rm -f "${PDS_DEINITIALIZE_RUNNING}"
			exit 0
		fi

		#Disconnect all devices in CONTROLLER_NQN_LOG file. This speeds up cleanup as disconnects happen on nqn, instead of device, that would handle multiple disconnects in case of multipath.
		for nqn in ${pds_vol_nqns}; do
			echo "${PDS_STRING} Disconnecting NVMe-oF device with nqn: ${nqn}"
			nvme disconnect -n ${nqn}
		done

		#Disconnect all remaining PVL devices. This is to make sure that unlogged devices does not get missed out.
		connected_pvl_devices=$(nvme list | grep PVL | awk '{print $1}' | awk -F "/" '{print $3}')
		for device in ${connected_pvl_devices}; do
			echo "${PDS_STRING} Disconnecting NVMe-oF device ${device}"
			nvme disconnect -d ${device}
		done

		# To make sure that none of the NQN remain connected.
		sleep 20
	done

	rm -f "${CONTROLLER_NQN_LOG}"
	rm -f "${PDS_DEINITIALIZE_RUNNING}"
	exit 0
}

stop_and_exit()
{
	echo "<1>${PDS_STRING} Disconnecting connected devices."
	touch "${PDS_DEINITIALIZE_RUNNING}"

	pds_vol_nqns=($(echo "$@" | tr ' ' '\n' | uniq | tr '\n' ' '))

	#Disconnect all devices in CONTROLLER_NQN_LOG file. This speeds up cleanup as disconnects happen on nqn, instead of device, that would handle multiple disconnects in case of multipath.
	for nqn in ${pds_vol_nqns[@]}; do
		#echo "${PDS_STRING} Disconnecting NVMe-oF device with nqn: ${nqn}"
		nvme disconnect -n ${nqn}
	done

	rm -f "${PDS_DEINITIALIZE_RUNNING}"
	exit 1
}

nvme_core_module_parameter="io_timeout=${io_timeout}"
if [[ $kernel_version -ge 5 ]]; then
	nvme_core_module_parameter="$nvme_core_module_paramater multipath=N"
fi

function check_and_load_module()
{
	pds_module_not_loaded=true
	pds_nvme_module_not_loaded=true

	is_loaded=`lsmod | grep -i $1`
	if [[ -z $is_loaded ]]; then
		if [[ "$1" == "nvme_${transport}" ]]; then
			echo "${PDS_STRING} Loading NVMe core module with IO Timeout to ${io_timeout}"
			nvme_core_loaded=`modprobe -v nvme_core $nvme_core_module_parameter`
			if [[ -z "$nvme_core_loaded" ]]; then
				echo ${io_timeout} > "/sys/module/nvme_core/parameters/io_timeout"
			fi
			modprobe -v nvme_${transport}
			if [ $? -ne 0 ]; then
				echo "${PDS_STRING} Failed to load NVMe-oF stack. Following could be potential causes:"
				echo "${PDS_STRING} 1. Loaded modules and on-disk modules are incompatible."
				echo "${PDS_STRING} 2. Possible direct attached NVMe SSD with root FS mounted."
				echo "${PDS_STRING} Exiting with error..."
				exit 1
			else
				modprobe -v nvme
			fi
			pds_nvme_module_not_loaded=false
		else
			modprobe -v "$1"
		fi
		pds_module_not_loaded=false
		echo "${PDS_STRING} Module $1 loaded!"
	fi

	if $pds_need_network_restart; then
		modprobe -rv "$1"
		modprobe -v "$1"
		echo "${PDS_STRING} Module $1 reloaded!"
	else
		loaded_driver_version=`modinfo $1 | head -1 | awk '{print $2}' | tr "/" " " | awk '{print $3}'`
		if [[ "$loaded_driver_version" != "$kernel" ]]; then
			echo "<1>${PDS_STRING} Loaded $1 driver version does not match with the kernel version! Exiting the Service..."
			exit 1
		fi

		if $pds_module_not_loaded; then
			echo "${PDS_STRING} Module $1 already loaded. No need to Reload!"
		fi

		if [[ "$1" == "nvme_${transport}" ]]; then
			if $pds_nvme_module_not_loaded; then
				echo "${PDS_STRING} Setting NVMe core module IO Timeout to ${io_timeout}"
				echo ${io_timeout} > "/sys/module/nvme_core/parameters/io_timeout"
		        fi
		fi
	fi
}

function get_device_from_list()
{
	devices=$(nvme list | awk -F "/" '{print $3}' | awk -F " " '{print $1}')
	echo ${devices:1:L-2}
}

function is_ip_reachable() 
{
	ip_check_response=0
	for ip in ${unreachable_controller_ips[@]};do
    	if [[ $ip == $1 ]];then
			ip_check_response=1
			break
    	fi
 	done
	echo $ip_check_response
}

if [ -f ${PDS_INIT_DONE} ];then
    if [ -f ${PDS_TMR_RUNNING} ];then
        echo "${PDS_STRING} The PDS nvme timer seems to be in a hung state, failing the attempt to restart the pds service via systemctl"
        exit 1
    else
        echo "${PDS_STRING} The PDS service is being restarted via systemctl"
    fi
else
    echo "${PDS_STRING} The PDS service is starting after a reboot"
    if [ -f ${PDS_TMR_RUNNING} ];then
    	echo "${PDS_STRING} Removing the file ${PDS_TMR_RUNNING} as the service is starting after a reboot"
	rm -f ${PDS_TMR_RUNNING}
    fi
fi

check_and_load_module mlx4_ib
check_and_load_module mlx5_ib
check_and_load_module nvme_${transport}

if $pds_need_network_restart; then
	# If the first controller is not reachable restart network.
	for ctrlr_ip_addr in ${cntrlr_ip_addr_list[@]} ; do
		# To make sure that all the modules are loaded before checking network reachability.
		sleep 10
		ping_response=`ping -c 1 ${ctrlr_ip_addr} | grep "64 bytes from"`
		if [[ $ping_response ]]; then
			echo "${PDS_STRING} Network is Reachable!"
		else
			networkService_present=`systemctl list-units | grep network.service`
			if [[ -n $networkService_present ]]; then
				echo "<1>${PDS_STRING} Network Unreachable! Restarting network service."
				systemctl restart network
			else
				newtworkService_present=`systemctl list-units | grep NetworkManager.service`
				if [[ -n $networkService_present ]]; then
					echo "${PDS_STRING} Restarting NetworkManager service."
					systemctl restart NetworkManager
				fi
			fi
		fi
		break
	done
fi

echo "${PDS_STRING} Trying to see if the controllers are accessible..."

#Initialize a list to fetch controller IPs that cannot be reached
unreachable_controller_ips=()
#Check if the controllers in cntrlr_ip_addr_list are accessible
for ctrlr_ip_addr in ${cntrlr_ip_addr_list[@]} ; do
	echo "${PDS_STRING} Checking if ${ctrlr_ip_addr} is accessible!"
	COUNTER=1
	# Check 10 times if the controller in controller list is up or not.
	while [[ $COUNTER -lt 10 ]]; do
		ping_response=`ping -c 1 ${ctrlr_ip_addr} | grep "64 bytes from"`
		if [[ $ping_response ]]; then
			echo "${PDS_STRING} Controller : ${ctrlr_ip_addr} is accessible!"
			break
		fi
		let COUNTER=COUNTER+1
	done
	if [[ $ping_response ]]; then
		echo "${PDS_STRING} Start Connecting..."
	else
		echo "<1>${PDS_STRING} Controller ${ctrlr_ip_addr} is not accessible! Please check pds.conf file."
		unreachable_controller_ips+=($ctrlr_ip_addr)
		echo ${unreachable_controller_ips[@]}
		#exit 1 #Commenting the exit 1 so that in case controllers are unreachable the service continues
	fi
done

#Check if the controllers in nqns_cntrlr_ip_list are accessible
for ctrlr_ip_addr in ${nqns_cntrlr_ip_list[@]} ; do
	echo "${PDS_STRING} Checking if ${ctrlr_ip_addr} is accessible!"
	COUNTER=1
	while [[ $COUNTER -lt 10 ]]; do
		ping_response=`ping -c 1 ${ctrlr_ip_addr} | grep "64 bytes from"`
		if [[ $ping_response ]]; then
			echo "${PDS_STRING} Controller : ${ctrlr_ip_addr} is accessible!"
			break
		fi
		let COUNTER=COUNTER+1
	done
	if [[ $ping_response ]]; then
		echo ""
	else
		echo "<1>${PDS_STRING} Controller ${ctrlr_ip_addr} is not accessible! Please check pds.conf file."
		unreachable_controller_ips+=($ctrlr_ip_addr)
		echo ${unreachable_controller_ips[@]}
		#exit 1 #Commenting the exit 1 so that in case controllers are unreachable the service continues
	fi
done

#Keep Track of Connections
NQN_ARRAY=()
IP_ASSOCIATED_TO_NQN_ARRAY=()

#Connect all the NQN's in the cntrlr_ip_addr_list provided in the pds.conf file.
if (( ${#cntrlr_ip_addr_list[@]} > 5 )); then
	SLEEP_ON_CONNECT=false
fi
for ctrlr_ip_addr in ${cntrlr_ip_addr_list[@]} ; do
	ip_reachable=$(is_ip_reachable $ctrlr_ip_addr)
	if [[ $ip_reachable == "1" ]];then
		continue
	fi

	echo "${PDS_STRING} Discovering NQNs at ${ctrlr_ip_addr}:"
	nqns=$(nvme discover -t ${transport} -a ${ctrlr_ip_addr})
	if [[ $? -ne 0 ]]; then
		echo "<1>${PDS_STRING} Failed to discover nqn's at ${ctrlr_ip_addr}! Please check controller configuration and restart pds.service."
		stop_and_exit "${NQN_ARRAY[@]}"
	fi
	nqns=$(echo "${nqns}" | grep -i nqn | awk '{ print $2 }')
	if [[ "$nqns" ]] ; then
		found_nqns="${nqns//$'\n'/ }"
		echo "${PDS_STRING} Found NQNs = ${found_nqns} at ${ctrlr_ip_addr}"
		for nqn in $nqns; do
			echo "${PDS_STRING} Connecting ${nqn} at ${ctrlr_ip_addr}"
			connect_attempt=0
			sleep_time=0
			while [[ $connect_attempt -lt 4 ]]; do
				$(nvme connect -t ${transport} -a ${ctrlr_ip_addr} -n ${nqn} -i ${num_io_queue})
				if [[ $? -ne 0 && $? -ne 142 ]]; then
					if [[ $connect_attempt -eq 3 ]]; then
						echo "<1>${PDS_STRING} Failed to connect NQN ${nqn} at ${ctrlr_ip_addr}! Please check NQN & Controller configuration and restart pds.service."
						stop_and_exit "${NQN_ARRAY[@]}"
					fi
				else
					break
				fi
				sleep_time=$(echo $sleep_time 0.5 | awk '{print $1 + $2}')
				sleep $sleep_time
				let connect_attempt=connect_attempt+1
			done

			echo "${PDS_STRING} Connected ${nqn} at ${ctrlr_ip_addr}"
			NQN_ARRAY+=(${nqn})
			IP_ASSOCIATED_TO_NQN_ARRAY+=(${ctrlr_ip_addr})
			if $SLEEP_ON_CONNECT; then
				sleep ${SLEEP_TIME}
			fi
		done
	fi
done

#Connect to specific NQN's in the nqns_list provided in the pds.conf file.
if (( ${#nqns_cntrlr_ip_list[@]} > 5 )); then
        SLEEP_ON_CONNECT=false
fi
for nqn in ${nqns_list[@]} ; do
	echo "${PDS_STRING} Connecting NQN: ${nqn}:"
	for ctrlr_ip_addr in ${nqns_cntrlr_ip_list[@]} ; do
		ip_reachable=$(is_ip_reachable $ctrlr_ip_addr)
        if [[ $ip_reachable == "1" ]];then
                continue
        fi

		nqns=$(nvme discover -t ${transport} -a ${ctrlr_ip_addr})
		if [[ $? -ne 0 ]]; then
			echo "<1>${PDS_STRING} Failed to discover nqn's at ${ctrlr_ip_addr}! Please check controller configuration and restart pds.service."
			stop_and_exit "${NQN_ARRAY[@]}"
		fi
		nqns=$(echo "${nqns}" | grep -i nqn | awk '{ print $2 }')
		if [[ "$nqns" ]] ; then
			nqn_on_ctrlr=`echo "${nqns}" | grep -o $nqn`
			if [[ $nqn_on_ctrlr ]]; then
				echo "${PDS_STRING} Connecting ${nqn} at ${ctrlr_ip_addr}"

				connect_attempt=0
				sleep_time=0
				while [[ $connect_attempt -lt 4 ]]; do
					$(nvme connect -t ${transport} -a ${ctrlr_ip_addr} -n ${nqn} -i ${num_io_queue})
					if [[ $? -ne 0 && $? -ne 142 ]]; then
						if [[ $connect_attempt -eq 3 ]]; then
							echo "<1>${PDS_STRING} Failed to connect NQN ${nqn} at ${ctrlr_ip_addr}! Please check NQN & Controller configuration and restart pds.service."
							stop_and_exit "${NQN_ARRAY[@]}"
						fi
					else
						break
					fi
					sleep_time=$(echo $sleep_time 0.5 | awk '{print $1 + $2}')
					sleep $sleep_time
					let connect_attempt=connect_attempt+1
				done

				echo "${PDS_STRING} Connected ${nqn} at ${ctrlr_ip_addr}"
				NQN_ARRAY+=(${nqn})
				IP_ASSOCIATED_TO_NQN_ARRAY+=(${ctrlr_ip_addr})
				if $SLEEP_ON_CONNECT; then
					sleep ${SLEEP_TIME}
				fi
			fi
		fi
	done
done

#Check for last connection. If the device corresponsing to last device is up, then go ahead and generate log.
BREAKWHILE=false
while (( ${#NQN_ARRAY[@]} )); do
	nvme_devices=( $(grep -rl "${NQN_ARRAY[-1]}" ${PDS_NVME_FABRICS_PATH}/*/subsysnqn 2>/dev/null | awk -F "/" '{print $7}') )
	for connected_nvme_device in ${nvme_devices[@]} ; do
		conn_ctrlr_ip=$(cat ${PDS_NVME_FABRICS_PATH}/${connected_nvme_device}/address | awk -F "," '{print $1}' | awk -F "=" '{print $2}')
		if [[ "${conn_ctrlr_ip}" == "${IP_ASSOCIATED_TO_NQN_ARRAY[-1]}" ]] ; then
			BREAKWHILE=true
			break
		fi
	done
	if $BREAKWHILE ; then
		break
	fi
	sleep 1
done

#Generate log of connected pavilion devices
>/etc/pds/pds_nvmeof_nqn_list.log
connected_pvl_nvme_devices=$(nvme list | grep "PVL" | awk -F "/" '{print $3}' | awk -F " " '{print substr($1, 1, length($1)-2)}')
for connected_nvme_device in ${connected_pvl_nvme_devices[@]} ; do
	subsysnqn=$(cat ${PDS_NVME_FABRICS_PATH}/${connected_nvme_device}/subsysnqn)
	ctrlr_ip_addr=$(cat ${PDS_NVME_FABRICS_PATH}/${connected_nvme_device}//address | awk -F "," '{print $1}' | awk -F "=" '{print $2}')
	echo "${subsysnqn} ${ctrlr_ip_addr} ${connected_nvme_device}" >> ${CONTROLLER_NQN_LOG}
done

#Add the unreachable controllers to the log file

for controller_ip in ${unreachable_controller_ips[@]}
do
    echo "XXXX ${controller_ip} nvmeX" >> ${CONTROLLER_NQN_LOG}
done

touch "${PDS_INIT_DONE}"
