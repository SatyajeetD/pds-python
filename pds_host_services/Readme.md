host_init_service
Location: svn://172.25.28.60/acadia_kernel/main/pavilion/nvmeof/host_init_services/
Building rpm:
    * svn checkout ...
    * Go inside host_init_services folder
    * run './build_rpm.sh [<file-system>] [<client>]'
        Specify the file system that is dependent on. For example
        - gpfs.service
	Specify the client that we are building it for. Example
	- mg ( if building it for meadowgate )
    * Example of build rpm: "./build_rpm.sh gpfs.service mg"
    * The paramaters are optional. Should be provided only when needed.
    * Output will be stored at root in a folder named builtrpm-version (ex:builtrpm-1.8)

# Documentation for PDS Service
# Version:1.8

A step-by-step guide to install and run service

  rpm -i PDS_NVMEoF_SERVICE-1.8.8468-1.el7.x86_64.rpm
  Edit pds.conf file at /etc/pds/ as per the chassis setup configuration.
  systemctl start pds.service

What does the PDS service installer do?
1. Install does the following:
    a. The installer installs the following files
       (Description of each file is in the next section):
          * pds.conf
          * pds_initialize.sh
          * pds_deinitialize.sh
          * pds_nvmeof_tmr.sh
          * pds.service
    b. The installer creates a cronjob entry running every 5 minutes that check and makes sure all NVMeOF connections are up and running.
    c. Creates dependencies on services that require NVMeOF Volumes (for example gpfs service).
    d. Enable PDS service
    e. For starting PDS service user has to update the pds.conf file as per the setup and issue command "systemctl start pds.service".

2. Upgrade does the following:
    a. The Upgrade installs following files
       (Description of each file is in the next section):
          * pds_initialize.sh
          * pds_deinitialize.sh
          * pds_nvmeof_tmr.sh
          * pds.service
    b. The installer creates a cronjob entry running every 5 minutes that check and makes sure all NVMeOF connections are up and running.
    c. Creates dependencies on services that requires NVMeOF Volumes (for example gpfs service).
    d. Restarts PDS service

3. PDS installer installs following files:
        pds.conf
        Location: /etc/pds/
        Description:
            This is the configuration file for PDS NVMeOF subsystem which contains the following PDS Array configuration:
                a. List of Controllers IP addresses and/or NQNs from chassis setup configuration in the environment
                b. IO queue count
                c. The version of pds.conf

        pds_initialize.sh
        Location: /usr/bin/
        Description:
            This is the main service script from the host init service package. It has the following functionalities:
                a. Check if required modules for NVMeOF are loaded; if not, then modules will be loaded with io_timeout=90.
                b. Check if multipath from nvme is Enabled, if enabled, reinstalls NVMeOF drivers with multipath=N.
                c. Check if the network modules are up; if not up, then it restart the network service.
                d. Check if the network path is available for all the listed controllers using ping; if not then retry 10 times for response; otherwise log the error in journalctl and connect the accessible volumes.
                e. As of now, there are the following 2 ways to do nvme connect to the controllers and NQN:
                    * Controllers list: If all the NQN on the controllers are required to be connected then populate the cntrlr_ip_addr_list with controller IP addresses in the pds.conf file
                    * If there is a need for specific NQN and controller to be connected then populate nqns_list for NQN and corresponding controller's IP address in nqns_cntrlr_ip_list in the pds.conf file
                f. Before connecting to the controller this service will figure out available NQNs to connect, then connects one by one and saves them as well.
                g. As the setup demands for large HPC environment, the number of IO queues can be configured by initializing num_io_queue in the pds.conf file (by default it is set to 8)
                h. This will take care of connecting multipath connections for all NVMeOF devices exposed
                i. If an interrupt is sent to the service when pds_initialize is executing, then it will disconnect all the connected nvme devices, wait 20 seconds and repeat it thrice to ensure all the nvme devices are disconnected.

        pds_deinitialize.sh
        Location: /usr/bin/
        Description:
            This script performs stop functionality of pds.service. Following are the functionalities of this script:
                a. Collect all the connected NVMeOF devices.
                b. Issue NVMEoF disconnects on all NVMeOF devices.
                c. And removes the files created by initializing operations.

        pds_nvmeof_tmr.sh
        Location: /usr/bin/
        Description:
            NVMeOF in-box stack tries to reconnect till 10 minutes in case any issue/disconnect happens, but after that, the host stops the attempt to reconnect.
	    For that reason, this cronjob is needed.
            This cronjob script has the following functionalities:
                a. Check every 5 mins, if any of the PDS volumes got disconnected.
                b. If yes then try to reconnect all of them. If some of the NQNs are already connected then ignore otherwise connect
                c. Logs all the activities in journalctl (To check the logs for crond run command "journalctl | grep crond.service")

        pds.service
        Location: /etc/systemd/system/
        Description:
            This is a system control service file; which has the following functionalities:
                 a. Starting and stopping host init service.
                 b. Creates and makes the other service dependencies for which the NVMeOF devices are required to be present (in the current case like multiuser and gpfs).

Uninstalling the RPM.
    1. CAUTION: This is a destructive operation which will delete all the configuration and setup files installed and created by the operation
    2. Run the following command as superuser to remove PDS Service:
          rpm -e `rpm -qa | grep PDS`
    3. Reverts the service's script which is changed during the installation.
    4. Uninstallation of PDS service will do the following:
        a. Disable PDS service
        b. Stops PDS service
        c. Removes all the files installed and created by the operational part of the service
        d. This will also remove the configuration setup that has information about the chassis setup i.e pds.conf file.

Upgrading the RPM.
    1. Run the following command to upgrade the RPM.
          rpm -U PDS_NVMEoF_SERVICES-1.x-1.el7.x86_64.rpm
    2. Upgrading of PDS Service package will do the following:
          Install all the files except pds.conf file
          restart pds.service 
