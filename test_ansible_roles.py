import os
import subprocess
import yaml
import shutil, os
from pathlib import Path
import yaml
import glob

def fuck_with_filenames (dir):
    
    ## This perturbation reads all yaml files within a testsuite and fucks around with the file names to potentially introduce errors in this way
    
    assert dir
    
    name_map = {}
    ## Get list of filenames that are copied over
    
    for filename in os.listdir(os.path.join(dir, "files")):
        name_map[filename] = 0
    print(name_map)       
    
    ## Now go through the rest of the yml files and play around with the filenames
    
    yaml_files = glob.glob(f"{dir}/**/*.yml")
    
    for file in yaml_files:
        print(file)
        with open(file, 'r') as stream:
            data_loaded = yaml.safe_load(stream)

        
        for i in data_loaded:
            print(i)
            print("..........")
    
        assert False
    

def perturb_tests (role_path, perturbation = [], ansible_path = ".."):
    '''
    copy the test directory to a local temporary dir and maybe make changes to it. This temp dir (.mnt/test) Will be mounted to the container at run time and these tests will be performed 
    '''    
    # copy subdirectory example
    from_directory = role_path
    to_directory = "mnt/test"
    # Remove centents of temp directory if it already exists
    if os.path.exists(to_directory):    
        shutil.rmtree(to_directory) 
    shutil.copytree(from_directory, to_directory)
        
    ## Apply perturbations
    fuck_with_filenames(role_path)    

def read_config():
    with open('config.yaml') as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
    return config

def get_role_paths(config):
    core_base_path = '/ansible/test/integration/targets/'
    core_role_paths = [core_base_path + role_path for role_path in config['core_modules']]
    community_base_path = '/community/tests/integration/targets/'
    community_role_paths = [community_base_path + role_path for role_path in config['community_modules']]
    return core_role_paths + community_role_paths

def generate_playbook(role_path):
    playbook = f"""
---
- hosts: localhost
  roles:
    - role: '{role_path}'
"""
    with open('/mnt/playbook.yml', 'w') as playbook_file:
        playbook_file.write(playbook)

def run_command(command):
    subprocess.run(command, shell=True)

def create_output_folder():
    output_folder = 'output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

def run_ansible_role_in_docker(role_path, command, command_id, perturbation = []):
    generate_playbook(role_path)
    perturb_tests(role_path, perturbation)
    role_name = os.path.basename(os.path.normpath(role_path))
    output_filename = f"output/{role_name}_{command_id}_output.txt"
    # Store the executed command in the output file
    with open(output_filename, 'w') as output_file:
        output_file.write(command)
        
    ## This command overwrites the existing ansible test case with our mounted testcase:
    symlink = f"ln -s -f /mnt/test {role_path}"
    
    print("symlink: ", symlink)

    docker_command = f"""
docker run --rm -it \
    -v $(pwd)/mnt:/mnt \
    ansible \
    /bin/bash -c "{command} && {symlink} && ansible-playbook /mnt/playbook.yml" >> {output_filename}
"""
    run_command(docker_command)
#    assert False

def process_output_files():
    output_folder = 'output'
    output_files = os.listdir(output_folder)
    no_errors = True
    for output_file in output_files:
        with open(f"{output_folder}/{output_file}") as output:
            # The executed command is stored in the first line of the output file
            command = output.readline()
            if 'failed=0' not in output.read():
                no_errors = False
                print(f"BUG FOUND in: {output_file}, with command: {command}")
    if no_errors:
        print("No bugs found :(")

def main():
    config = read_config()
    role_paths = get_role_paths(config)
    create_output_folder()

    for role_path in role_paths:
        for command_id, command in enumerate(config['perturbation_commands']):
            print(f"Testing role: {role_path} with command: {command}")
            run_ansible_role_in_docker(role_path, command, command_id)
    
    process_output_files()

if __name__ == '__main__':
    main()
