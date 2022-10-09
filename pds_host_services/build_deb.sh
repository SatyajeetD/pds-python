#!/bin/bash

#CONSTANTS
FILESYSTEM=""
CLIENT=""
RPM_NAME="PDS_NVMEoF_SERVICE"
RPM_VERSION=""
CURR_DIR=$(pwd)

BIN_FOLDER="${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin"
SERVICE_FOLDER="${CURR_DIR}/PDS-NVMeoF-SERVICE/etc/systemd/system"
PDS_FOLDER="${CURR_DIR}/PDS-NVMeoF-SERVICE/etc/pds"
FS_NAME=""

#Check if the dpkg build tools are installed or not

if [[ $1 == "mg" ]]; then
	CLIENT=$1
	if [[ -n $2 ]]; then
		FILESYSTEM=$2
		FS_NAME=`echo "$2" | cut -d'.' -f1`
	fi
else
	FILESYSTEM=$1
	FS_NAME=`echo "$1" | cut -d'.' -f1`
	if [[ -n $2 ]]; then
		CLIENT=$2
	fi
fi

RPM_VERSION=$(awk '/pds_service_version/ {print $2}' pds_service_version.txt).$(svn info | grep Revision | awk '{print $2}')

if [[ -n $CLIENT ]]; then
	RPM_NAME="PDS_NVMEoF_SERVICE-${CLIENT}"
fi
if [[ -n $FILESYSTEM ]]; then
	RPM_NAME="${RPM_NAME}-${FS_NAME}"
fi
RPM=${RPM_NAME}
RPM_NAME="${RPM_NAME}-${RPM_VERSION}"

#Creating dpkg build directory for deb package build to run successfully.
mkdir -p ${CURR_DIR}/PDS-NVMeoF-SERVICE
mkdir -p ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin
mkdir -p ${CURR_DIR}/PDS-NVMeoF-SERVICE/etc/pds
mkdir -p ${CURR_DIR}/PDS-NVMeoF-SERVICE/etc/systemd/system

#Copy files at appropriate location
cp -rf DEBIAN/ ${CURR_DIR}/PDS-NVMeoF-SERVICE
cp -rf SCRIPTS/pds_deinitialize.sh ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin
cp -rf SCRIPTS/pds_nvmeof_tmr.sh ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin
cp -rf SRC/pds.service ${CURR_DIR}/PDS-NVMeoF-SERVICE/etc/systemd/system
cp -rf SRC/sample_pds.conf ${CURR_DIR}/PDS-NVMeoF-SERVICE/etc/pds

if [[ ${CLIENT} == "mg" ]]; then
	cp -rf SCRIPTS/pds_initialize_mg.sh ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin
	mv ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin/pds_initialize_mg.sh ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin/pds_initialize.sh
else
	cp -rf SCRIPTS/pds_initialize.sh ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin
fi

if [[ -n $FILESYSTEM ]]; then
	cat ${SERVICE_FOLDER}/pds.service | sed "s/Before=/Before=${FILESYSTEM} /g" >${SERVICE_FOLDER}/sample_pds.service
	mv -f ${SERVICE_FOLDER}/sample_pds.service ${SERVICE_FOLDER}/pds.service
	cat ${SERVICE_FOLDER}/pds.service | sed "s/WantedBy=/WantedBy=${FILESYSTEM} /g" >${SERVICE_FOLDER}/sample_pds.service
	mv -f ${SERVICE_FOLDER}/sample_pds.service ${SERVICE_FOLDER}/pds.service
fi

if [[ ${CLIENT} == "mg" ]]; then
	cat ${SERVICE_FOLDER}/pds.service | sed "s/Before=local-fs.target/Before= /g" >${SERVICE_FOLDER}/sample_pds.service
	mv -f ${SERVICE_FOLDER}/sample_pds.service ${SERVICE_FOLDER}/pds.service
	cat ${PDS_FOLDER}/sample_pds.conf | sed "s/num_io_queue=8/num_io_queue=4 /g" >${PDS_FOLDER}/sample.conf
	mv -f ${PDS_FOLDER}/sample.conf ${PDS_FOLDER}/sample_pds.conf
fi

# Set appropriate access to the files to be installed
chmod 0100 ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin/pds_initialize.sh
chmod 0100 ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin/pds_deinitialize.sh
chmod 0100 ${CURR_DIR}/PDS-NVMeoF-SERVICE/usr/bin/pds_nvmeof_tmr.sh
chmod 0644 ${CURR_DIR}/PDS-NVMeoF-SERVICE/etc/systemd/system/pds.service
chmod 0200 ${CURR_DIR}/PDS-NVMeoF-SERVICE/etc/pds/sample_pds.conf
chmod +x  ${CURR_DIR}/PDS-NVMeoF-SERVICE/DEBIAN/control
chmod +x  ${CURR_DIR}/PDS-NVMeoF-SERVICE/DEBIAN/prerm
chmod +x  ${CURR_DIR}/PDS-NVMeoF-SERVICE/DEBIAN/postinst

#Change Version in the control file of the package
cat ${CURR_DIR}/DEBIAN/control | sed -e "s/%VERSION_MARKER%/${RPM_VERSION}/g" >${CURR_DIR}/DEBIAN/tmpControl
mv -f ${CURR_DIR}/DEBIAN/tmpControl ${CURR_DIR}/DEBIAN/control

#Build the package
dpkg-deb -b PDS-NVMeoF-SERVICE ${RPM_NAME}-amd64.deb

rm -rf ${CURR_DIR}/PDS-NVMeoF-SERVICE
