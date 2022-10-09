import subprocess
import logging

#Get the logger created via the connector script
logger = logging.getLogger('pds.module_checker')

#check if modules are present and if not load the necessary modules
#Add mellanox modules check
def check_nvme_modules_and_load():
	#Code for nvme modules
	p1=subprocess.Popen(['lsmod'],stdout=subprocess.PIPE)
	p2=subprocess.Popen(['grep','nvme'],stdin=p1.stdout,stdout=subprocess.PIPE)
	p1.stdout.close()
	returncode=p2.wait()

	#If returncode is non-zero, it means the modules are not loaded ,load the modules
	if returncode != 0:
		load_modules=subprocess.Popen(['modprobe','nvme_rdma'],stdout=subprocess.PIPE)
		result=load_modules.wait()
		if result == 0:
			logger.info("Loading nvmeof modules successful")
			return 0
		else:
			logger.error("Error loading modules, please check the system state")
			return -1
	else:
		logger.info("NVMeoF modules already present, pds service can proceed")
		return 0

def check_mlx_modules_and_load():
	#Code for Mellanox modules
	p1=subprocess.Popen(['lsmod'],stdout=subprocess.PIPE)
	p2=subprocess.Popen(['grep','mlx4_ib'],stdin=p1.stdout,stdout=subprocess.PIPE)
	p1.stdout.close()
	mlx4=p2.wait()
	p1=subprocess.Popen(['lsmod'],stdout=subprocess.PIPE)
	p2=subprocess.Popen(['grep','mlx5_ib'],stdin=p1.stdout,stdout=subprocess.PIPE)
	p1.stdout.close()
	mlx5=p2.wait()

	if mlx4==0 and mlx5==0:
		logger.info('The Mellnox modules mlx4_ib and mlx5_ib are already loaded')
		return 0
	elif mlx4!=0 and mlx5==0:
		#Loading Mellanox module - mlx4_ib
		mlx4_load=subprocess.Popen(['modprobe','mlx4_ib'],stdout=subprocess.PIPE)
		mlx4_load_result=mlx4_load.wait()
		if mlx4_load_result == 0:
			logger.info("Module mlx5_ib already loaded, mlx4_ib loaded succesfully")
		return 0
	elif mlx5!=0 and mlx4==0:
		mlx5_load=subprocess.Popen(['modprobe','mlx5_ib'],stdout=subprocess.PIPE)
		mlx5_load_result=mlx5_load.wait()
		if mlx5_load_result == 0:
			logger.info("Module mlx4_ib already loaded, mlx5_ib loaded succesfully")
		return 0
	else:
		mlx4_load=subprocess.Popen(['modprobe','mlx4_ib'],stdout=subprocess.PIPE)	
		mlx4_load_result=mlx4_load.wait()
		mlx5_load=subprocess.Popen(['modprobe','mlx5_ib'],stdout=subprocess.PIPE)	
		mlx5_load_result=mlx5_load.wait()
		if mlx4_load_result==0 and mlx5_load_result==0:
			logger.info("Module mlx4_ib and mlx5_ib have been loaded successfully ")
		return 0
	
	

def check_nvme_util():
#Also check for installable like rpm or debian package.
#Identify if the system type is rpm based or dpkg based
	system_type='rpm'
	p1=subprocess.Popen(['which','rpm'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
	if p1.wait()==0:
		logger.info("system is "+system_type+" based checking for nvme-cli rpm")
		rpm_list=subprocess.Popen(['rpm','-qa'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
		check_rpm=subprocess.Popen(['grep','nvme'],stdin=rpm_list.stdout,stdout=subprocess.PIPE)
		rpm_list.stdout.close()
		nvme_util_rpm_status=check_rpm.communicate()[0]
		if 'nvme-cli' in nvme_util_rpm_status:
			logger.info("nvme-cli rpm "+str(nvme_util_rpm_status.strip())+" is installed")
		else:
			return -1
	else:
		system_type='dpkg'
		p1=subprocess.Popen(['which','dpkg'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
		if p1.wait()==0:
                	logger.info("system is "+system_type+" based checking for nvme-cli package")
			dpkg_list=subprocess.Popen(['dpkg','-L'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
			check_dpkg=subprocess.Popen(['grep','nvme'],stdin=rpm_list.stdout,stdout=subprocess.PIPE)
			dpkg_list.stdout.close()
			nvme_util_dpkg_status=check_dpkg.communicate()[0]
			if 'nvme-cli' in nvme_util_dpkg_status:
				logger.info("nvme-cli package "+str(nvme_util_dpkg_status)+" is installed")
			else:
				return -1

	try:
		p1=subprocess.Popen(['nvme','--version'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
		if p1.wait() == 0:
			logger.info("nvme utility is installed")
			return 0
		else:
			logger.error("nvme utility missing, cannot proceed further")
			return -1
	except FileNotFoundError:
		logger.error("nvme util not installed")
		return -1
