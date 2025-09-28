import os
import paramiko
from read_yaml import get_config_values

host, user, key_file = get_config_values('devices.yaml')

client = paramiko.SSHClient()

client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

client.connect(hostname=host,username=user,key_filename=os.path.expanduser(key_file))

sftp = client.open_sftp()

print(sftp.listdir("."))

client.close()
