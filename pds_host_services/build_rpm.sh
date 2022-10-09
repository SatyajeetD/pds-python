#!/bin/bash

#CONSTANTS
SOURCE_FOLDER=${HOME}/rpmbuild/SOURCES
SRC_FOLDER=${HOME}/rpmbuild/SOURCES/SRC
SPECS_FOLDER=${HOME}/rpmbuild/SPECS
FILESYSTEM=""
CLIENT=""
RPM_NAME="PDS_NVMe-oF_SERVICE"
RPM=""
RPM_VERSION=""
CURR_DIR=$(pwd)
FS_NAME=""
#Check if the rpm build dependencyis installed or not
installedDependency=$(rpm -qa | grep -qw rpm-build-4 || yum -y install rpm-build)
installedDependency=$(rpm -qa | grep -qw rpmdev || yum install -y rpmdevtools rpmlint)

#Check number of arguments and exit if it is less than 3
if [[ $# -ne 3 ]];then
    if [[ $# -gt 1 ]];then
        echo "Invalid number of arguments, please check and rerun"
        #DEFINE AND CALL usage
        exit
    elif [[ $# == 1 ]];then
        if [[ $1 == "3.0" ]];then
            PDSVERSION="3.0"
            echo "PDS versions is ${PDSVERSION}"
        elif [[ $1 == "2.0" ]];then
            PDSVERSION="2.0"
            echo "PDS versions is ${PDSVERSION}"
        else
            echo "Invalid input for version number provided"
            exit
        fi
    else
        echo "Invalid number of arguments provided"
        exit
    fi
elif [[ $# == 3 ]];then
    #Check the version requested for build process, current supported versions are 2.0 and 3.0
    if [[ $3 == "3.0" ]];then
        echo "Initiating build process for PDS 3.0"
        PDSVERSION=$3
    elif [[ $3 == "2.0" ]];then
        echo "Initiating build process for PDS 2.0"
        PDSVERSION=$3
    else
        echo "Invalid PDS version requested or incorrect order of arguments supplied"
        #DEFINE AND CALL usage
        exit
    fi
    if [[ $1 = "mg" ]]; then
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
fi

minorVersion=$(cat minor_version.txt)
if [[ $PDSVERSION == "2.0" ]];then
    RPM_VERSION=$(awk '/pds_service_version/ {print $2}' v2.version).${minorVersion}
elif [[ $PDSVERSION == "3.0" ]];then
    RPM_VERSION=$(awk '/pds_service_version/ {print $2}' v3.version).${minorVersion}
fi
if [[ -n $CLIENT ]]; then
	RPM_NAME="PDS_NVMEoF_SERVICE-${CLIENT}"
fi

if [[ -n $FILESYSTEM ]]; then
	RPM_NAME="${RPM_NAME}-${FS_NAME}"
fi

RPM=${RPM_NAME}
RPM_NAME="${RPM_NAME}-${RPM_VERSION}"

#Cheching if there is already an rpm directory present in the root directory.
create_rpm_dir_structure()
{
	RPM_FOLDER=~/rpmbuild/
	if [[ -d $RPM_FOLDER ]]; then
		echo "rpm folder already present in root."
		echo "Continue to empty rpm folder? y/n"
		read option
		if [ "$option" == "y" ] ; then
			rm -rf $RPM_FOLDER
		else
			exit 0
		fi
	fi
}

setup_dev_env()
{
	echo "Creating RPM build directories in your home directory...."
	create_rpm_dir_structure
    echo $?
    echo "Tress"
	rpmdev-setuptree
    echo $?
}

copy_files_v2()
{
	cp -rf SRC/ ${SOURCE_FOLDER}
	cp -f SPECS/pdsnvmeof_v2.spec ${SPECS_FOLDER}
	cp -f SCRIPTS/pds_nvmeof_tmr.sh ${SRC_FOLDER}
	cp -f SCRIPTS/pds_deinitialize.sh ${SRC_FOLDER}

	if [[ ${CLIENT} == "mg" ]]; then
		cp -f SCRIPTS/pds_initialize_mg.sh ${SRC_FOLDER}
		mv ${SRC_FOLDER}/pds_initialize_mg.sh ${SRC_FOLDER}/pds_initialize.sh
	else
		cp -f SCRIPTS/pds_initialize.sh ${SRC_FOLDER}
	fi	
}

make_filesystem_changes()
{
	if [[ -n $FILESYSTEM ]]; then
		cat ${SRC_FOLDER}/pds.service | sed "s/Before=/Before=${FILESYSTEM} /g" > ${SRC_FOLDER}/sample_pds.service
		mv -f ${SRC_FOLDER}/sample_pds.service ${SRC_FOLDER}/pds.service
		cat ${SRC_FOLDER}/pds.service | sed "s/WantedBy=/WantedBy=${FILESYSTEM} /g" > ${SRC_FOLDER}/sample_pds.service
		mv -f ${SRC_FOLDER}/sample_pds.service ${SRC_FOLDER}/pds.service
	fi
	
	if [[ ${CLIENT} == "mg" ]]; then
		cat ${SRC_FOLDER}/pds.service | sed "s/Before=local-fs.target/Before= /g" >${SRC_FOLDER}/sample_pds.service
		mv -f ${SRC_FOLDER}/sample_pds.service ${SRC_FOLDER}/pds.service
		cat ${SRC_FOLDER}/sample_pds.conf | sed "s/num_io_queue=8/num_io_queue=4 /g" >${SRC_FOLDER}/sample.conf
		mv -f ${SRC_FOLDER}/sample.conf ${SRC_FOLDER}/sample_pds.conf
	fi
}

set_final_file_permissions_v2()
{
	chmod 0100  ${SRC_FOLDER}/pds_initialize.sh
	chmod 0100  ${SRC_FOLDER}/pds_deinitialize.sh
	chmod 0100  ${SRC_FOLDER}/pds_nvmeof_tmr.sh
	chmod 0644  ${SRC_FOLDER}/pds.service
	chmod 0200  ${SRC_FOLDER}/sample_pds.conf
}

copy_files_v3()
{
    cp -rf SRC/ ${SOURCE_FOLDER}
    cp -f SPECS/pdsnvmeof_v3.spec ${SPECS_FOLDER}
    cp -f py-pds/pds_reconnector.py ${SRC_FOLDER}
    cp -f py-pds/pds_disconnector.py ${SRC_FOLDER}
    cp -f py-pds/pds_connector.py ${SRC_FOLDER}
    cp -f py-pds/pds_host_operations.py ${SRC_FOLDER}
    cp -f py-pds/pds_logger.py ${SRC_FOLDER}
    cp -f py-pds/pds_module_checker.py ${SRC_FOLDER}
    cp -f py-pds/pds_constants.py ${SRC_FOLDER}
    cp -f py-pds/pds_config_updater.py ${SRC_FOLDER}
    cp -f py-pds/pds_mgmt.py ${SRC_FOLDER}

}

set_final_file_permissions_v3()
{
    chmod 0100  ${SRC_FOLDER}/pds_connector.py
    chmod 0100  ${SRC_FOLDER}/pds_disconnector.py
    chmod 0100  ${SRC_FOLDER}/pds_reconnector.py
    chmod 0100  ${SRC_FOLDER}/pds_config_updater.py
    chmod 0100  ${SRC_FOLDER}/pds_mgmt.py
    chmod 0644  ${SRC_FOLDER}/pds.service_v3
    chmod 0200  ${SRC_FOLDER}/sample_pds_config.json

}

if [[ $PDSVERSION == "2.0" ]];then
    setup_dev_env
    copy_files_v2
    echo "Copying the 2.0 pds.service file"
    cp ${SRC_FOLDER}/pds.service_v2 ${SRC_FOLDER}/pds.service
    echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    cat ${SRC_FOLDER}/pds.service
    echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    make_filesystem_changes
    set_final_file_permissions_v2
elif [[ $PDSVERSION == "3.0" ]];then
    setup_dev_env
    copy_files_v3
    echo "Copying the 3.0 pds.service file"
    cp ${SRC_FOLDER}/pds.service_v3 ${SRC_FOLDER}/pds.service
    echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    cat ${SRC_FOLDER}/pds.service
    echo "++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    make_filesystem_changes
    set_final_file_permissions_v3
fi
    
#build rpm
cd ${SOURCE_FOLDER}
output=`mv SRC/ ${RPM_NAME}`
tar -cvf "${RPM}.tar.gz" $RPM_NAME/

if [[ $PDSVERSION == "2.0" ]];then
    cat ${SPECS_FOLDER}/pdsnvmeof_v2.spec | sed -e "s/%NAME%/${RPM}/g" > ${SPECS_FOLDER}/pdsnvmeofrpm.spec
    mv -f ${SPECS_FOLDER}/pdsnvmeofrpm.spec ${SPECS_FOLDER}/pdsnvmeof_v2.spec
    cat ${SPECS_FOLDER}/pdsnvmeof_v2.spec | sed -e "s/%VERSION_MARKER%/${RPM_VERSION}/g" > ${SPECS_FOLDER}/pdsnvmeofrpm.spec
    mv -f ${SPECS_FOLDER}/pdsnvmeofrpm.spec ${SPECS_FOLDER}/pdsnvmeof_v2.spec
    cat ${SPECS_FOLDER}/pdsnvmeof_v2.spec | sed -e "s/%FILE_SYSTEM%/$1/g" > ${SPECS_FOLDER}/pdsnvmeofrpm.spec
    mv -f ${SPECS_FOLDER}/pdsnvmeofrpm.spec ${SPECS_FOLDER}/pdsnvmeof_v2.spec
    cat ${SPECS_FOLDER}/pdsnvmeof_v2.spec | sed -e "s/%MINOR_VERSION%/${minorVersion}/g" > ${SPECS_FOLDER}/pdsnvmeofrpm.spec
    mv -f ${SPECS_FOLDER}/pdsnvmeofrpm.spec ${SPECS_FOLDER}/pdsnvmeof_v2.spec
    rpmbuild -ba ${SPECS_FOLDER}/pdsnvmeof_v2.spec
elif [[ $PDSVERSION == "3.0" ]];then
    cat ${SPECS_FOLDER}/pdsnvmeof_v3.spec | sed -e "s/%NAME%/${RPM}/g" > ${SPECS_FOLDER}/pdsnvmeofrpm.spec
    mv -f ${SPECS_FOLDER}/pdsnvmeofrpm.spec ${SPECS_FOLDER}/pdsnvmeof_v3.spec
    cat ${SPECS_FOLDER}/pdsnvmeof_v3.spec | sed -e "s/%VERSION_MARKER%/${RPM_VERSION}/g" > ${SPECS_FOLDER}/pdsnvmeofrpm.spec
    mv -f ${SPECS_FOLDER}/pdsnvmeofrpm.spec ${SPECS_FOLDER}/pdsnvmeof_v3.spec
    cat ${SPECS_FOLDER}/pdsnvmeof_v3.spec | sed -e "s/%FILE_SYSTEM%/$1/g" > ${SPECS_FOLDER}/pdsnvmeofrpm.spec
    mv -f ${SPECS_FOLDER}/pdsnvmeofrpm.spec ${SPECS_FOLDER}/pdsnvmeof_v3.spec
    cat ${SPECS_FOLDER}/pdsnvmeof_v3.spec | sed -e "s/%MINOR_VERSION%/${minorVersion}/g" > ${SPECS_FOLDER}/pdsnvmeofrpm.spec
    mv -f ${SPECS_FOLDER}/pdsnvmeofrpm.spec ${SPECS_FOLDER}/pdsnvmeof_v3.spec
    rpmbuild -ba ${SPECS_FOLDER}/pdsnvmeof_v3.spec
fi
    
cd ${CURR_DIR}
cp $HOME/rpmbuild/RPMS/x86_64/PDS* .
rm -rf $HOME/rpmbuild
