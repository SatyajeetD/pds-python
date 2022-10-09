Name:           %NAME%
Version:        %VERSION_MARKER%
Release:        1%{?dist}
Group:		Development/Tools
License:        PDS
Source0:        %{name}.tar.gz
Packager:	Pavilion Data Systems Inc. <https://www.pavilion.io>
Vendor:		Pavilion Data Systems Inc.
URL:            https://www.pavilion.io
Summary:        PDS NVMe-oF Initialization Service

%description
Initialization service which ensures NVMe-oF volumes are connected at all times.

%global debug_package %{nil}

%prep
%setup

%build

%install
rm -rf $RPM_BUILD_ROOT

mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/etc/systemd/system
mkdir -p %{buildroot}/etc/pds

cp %{_builddir}/%{name}-%{version}/sample_pds_config.json %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/sample_pds_input.txt %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_connector.py %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_disconnector.py %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_reconnector.py %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds.service %{buildroot}/etc/systemd/system/pds.service
cp %{_builddir}/%{name}-%{version}/pds_constants.py %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_module_checker.py %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_logger.py %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_host_operations.py %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_config_updater.py %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_mgmt.py %{buildroot}/etc/pds

%post
if [ $1 == 1 ];then
	# RPM INSTALL
	cp /etc/pds/sample_pds_config.json /etc/pds/pds.conf
    cp /etc/pds/pds_mgmt.py /usr/sbin/
	systemctl enable pds.service
    crontab -l | grep -v 'tmr.sh'|crontab -
	crontab -l > file; echo '*/5 * * * * /etc/pds/pds_reconnector.py | systemd-cat' > file; crontab file
	echo "--------------------------------"
	echo "Please update the pds.conf file in /etc/pds as per the chassis/filesystem setup configuration."
	echo "--------------------------------"
	echo "run command 'systemctl start pds.service' to start the service after editing pds.conf"
	echo "--------------------------------"
elif [ $1 == 2 ];then
	# RPM UPGRADE
    crontab -l | grep -v 'tmr.sh'|crontab -
	/etc/pds/pds_config_updater.py
    cp /etc/pds/pds_mgmt.py /usr/sbin/
	crond_service=`crontab -l | grep '/etc/pds/pds_reconnector.py'`
	if [[ -z $crond_service ]]; then
		crontab -l > file; echo '*/5 * * * * /etc/pds/pds_reconnector.py | systemd-cat' > file; crontab file
	fi
	systemctl daemon-reload
	systemctl restart pds.service
	echo "--------------------"
	echo "Upgrading PDS_NVMeoF Initialization Service Package."
	echo "--------------------"
fi

%preun
if [ $1 == 0 ];then
	# RPM UNINSTALL
	crontab -l | grep -v '/etc/pds/pds_reconnector.py' | crontab -
	systemctl disable pds.service
	systemctl stop pds.service
    echo "REMOVING files"
	rm -f /etc/pds/pds.conf
    rm -f /etc/pds/pds_nvmeof_nqn_list.log
    #rm -rf /etc/pds/
else
	echo ""
fi

%files
/etc/pds
/etc/pds/pds_connector.py
/etc/pds/pds_disconnector.py
/etc/pds/pds_reconnector.py
/etc/pds/pds_config_updater.py
/etc/pds/pds_mgmt.py
/etc/systemd/system/pds.service

%changelog
