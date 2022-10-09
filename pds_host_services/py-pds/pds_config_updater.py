#!/usr/bin/env python
import json
import pds_host_operations
import pds_constants
import shutil
flag=0
with open(pds_constants.pds_config_file) as f:
	lines=f.readlines()
if 'Version=3' not in lines[0]:
        flag=1
if flag ==1:
    x=lines[3]
    x=x.strip().split('=')[1].strip('()').split()
    data={}

    data=pds_host_operations.pds_read_config('/etc/pds/sample_pds_config.json')
    data['Cluster1'][0]['controller_ips']=x
    constants=pds_host_operations.pds_get_constants()
    data['Constants']=constants
    with open('/etc/pds/sample_pds_config.json') as f:
        lines=f.readlines()
    d=json.dumps(data, indent=4, sort_keys=True)
    with open(pds_constants.pds_config_file,'w') as g:
        g.write('Version=3\n')
        g.write(lines[1])
        g.write(d)
        g.write('\n')
