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

cp %{_builddir}/%{name}-%{version}/sample_pds.conf %{buildroot}/etc/pds
cp %{_builddir}/%{name}-%{version}/pds_initialize.sh %{buildroot}/usr/bin
cp %{_builddir}/%{name}-%{version}/pds_deinitialize.sh %{buildroot}/usr/bin
cp %{_builddir}/%{name}-%{version}/pds_nvmeof_tmr.sh %{buildroot}/usr/bin
cp %{_builddir}/%{name}-%{version}/pds.service %{buildroot}/etc/systemd/system

%post
if [ $1 == 1 ];then
	# RPM INSTALL
	cp /etc/pds/sample_pds.conf /etc/pds/pds.conf
	systemctl enable pds.service
	crontab -l > file; echo '*/5 * * * * /usr/bin/pds_nvmeof_tmr.sh | systemd-cat' >> file; crontab file
	echo "--------------------------------"
	echo "Please update the pds.conf file in /etc/pds as per the chassis setup configuration."
	echo "--------------------------------"
	echo "run command 'systemctl start pds.service' to start the service after editing pds.conf"
	echo "--------------------------------"
elif [ $1 == 2 ];then
	# RPM UPGRADE
	crond_service=`crontab -l | grep '/usr/bin/pds_nvmeof_tmr.sh'`
	if [[ -z $crond_service ]]; then
		crontab -l > file; echo '*/5 * * * * /usr/bin/pds_nvmeof_tmr.sh | systemd-cat' >> file; crontab file
	fi
	if (( %MINOR_VERSION% > 21 )); then
		# Check if pds.conf file has io_timeout
		if ! grep -q 'io_timeout=' /etc/pds/pds.conf; then
			$(sed -i "s/Version=1/Version=2/g" /etc/pds/pds.conf)
			$(echo -e "\nio_timeout=600" >> /etc/pds/pds.conf)
		fi
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
	crontab -l | grep -v '/usr/bin/pds_nvmeof_tmr.sh' | crontab -
	rm -f /etc/pds/pds.conf
	systemctl disable pds.service
	systemctl stop pds.service
else
	echo ""
fi

%files
/etc/pds
/usr/bin/pds_initialize.sh
/usr/bin/pds_deinitialize.sh
/usr/bin/pds_nvmeof_tmr.sh
/etc/systemd/system/pds.service

%changelog
