#!/bin/bash

PDS_HOME_DIRECTORY=/etc/pds
PDS_TMR_RUNNING=${PDS_HOME_DIRECTORY}/pds_nvmeof_tmr_running
PDS_DEINITIALIZE_RUNNING=${PDS_HOME_DIRECTORY}/pds_nvmeof_deinitialize_running
CONTROLLER_NQN_LOG=${PDS_HOME_DIRECTORY}/pds_nvmeof_nqn_list.log
PDS_STRING="[pds nvme-of service]"

timer_counter=0
while [ -f "${PDS_TMR_RUNNING}" ] && [ $timer_counter -lt 5 ]
do
	echo "${PDS_STRING} Waiting for [pds nvme-of crond timer] to finish running with wait count [$timer_counter]."
        timer_counter=$((timer_counter+1))
        sleep 10
done
if [[ $timer_counter -eq 5 ]];then
	echo "${PDS_STRING} de_initialize wait for [pds nvme-of crond timer] expired, exiting."
        exit 1
fi

touch "${PDS_DEINITIALIZE_RUNNING}"

pds_vol_nqns=`cat ${CONTROLLER_NQN_LOG} | awk '{print $1}' | sort | uniq `
for nqn in ${pds_vol_nqns}; do
	echo "${PDS_STRING} Disconnecting NVMe-oF device ${nqn}"
	res=$(nvme disconnect -n ${nqn})
	echo "${PDS_STRING} ${res}"
done

rm -f "${PDS_DEINITIALIZE_RUNNING}"
rm -f "${CONTROLLER_NQN_LOG}"
