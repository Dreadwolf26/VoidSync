import yaml

def get_config_values(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
    
    for device in config['connections']:
        host_name = device['host']
        user_name = device['username']
        key_name  = device['key_file']
        allow_recursive_delete = device['allow_recursive_delete']


        #print(f"Host: {host_name}, User: {user_name}, Key: {key_name}")
    return host_name, user_name, key_name,allow_recursive_delete


