import paramiko
import os
from read_yaml import get_config_values

def create_connection(config_file="devices.yaml"):
    host, user, key_file, allow_recursive_delete = get_config_values(config_file)

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    client.connect(
        hostname=host,
        username=user,
        key_filename=os.path.expanduser(key_file)
    )

    sftp = client.open_sftp()
    print(f"SFTP connection established to {host}")

    # return all values so main can use allow_recursive_delete too
    return client, sftp, host, user, allow_recursive_delete
