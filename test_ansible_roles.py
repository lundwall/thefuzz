import os
import subprocess
import yaml
import shutil, os
from pathlib import Path
import yaml
import glob
import docker
import logging
from distutils.dir_util import copy_tree

from module import AnsibleModuleTest
from transformations import ChangeLangTransformation


def perturb_tests (role_path, perturbation):
    '''
    copy the test directory to a local temporary dir and maybe make changes to it. This temp dir (./mnt/test) Will be mounted to the container at run time and these tests will be performed 
    '''    
    # copy subdirectory example
    from_directory = role_path
    to_directory = "host/mnt/test"
    # Remove centents of temp directory if it already exists
    if os.path.exists(to_directory):    
        shutil.rmtree(to_directory) 
    shutil.copytree(from_directory, to_directory)
        
    module_test = AnsibleModuleTest(os.path.basename(role_path), "host/mnt/test")
    perturbation.transform(module_test)

    return

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

def generate_playbook(role_path, ip = "localhost"):
    playbook = f"""
---
- hosts: {ip}
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

def run_ansible_role_in_docker(role_path, perturbation):
    perturb_tests(role_path, perturbation)
    role_name = os.path.basename(os.path.normpath(role_path))
    # output_filename = f"output/{role_name}_{command_id}_output.txt"
    output_filename = f"host/mnt/logs.txt"

    # Store the executed command in the output file
    with open(output_filename, 'w') as output_file:
        output_file.write(perturbation.description + '\n')

    client = docker.from_env()

    ## Setup up the mounting for the tests. We mount a local directory to each of the containers to both provide and collect data for the experiments
    target_mount = [
        docker.types.Mount(
            "/mnt", f'{os.getcwd()}/target/mnt', 
            type = "bind")
        ]
    host_mount = [
        docker.types.Mount(
            "/mnt", f'{os.getcwd()}/host/mnt', 
            type = "bind")
        ]

    ## Launch both containers, the host and the target
    host = client.containers.run(
        "ansible:host", 
        mounts=host_mount,
        detach=True
    )
    
    ## Expose target's port 22 on port 2222 on local PC
    target = client.containers.run(
        "sshd", 
        ports = {'22/tcp': 2222},
        mounts=target_mount,
        detach=True
    )
    target_ip_add = client.containers.get(target.attrs["Id"]).attrs['NetworkSettings']['IPAddress']

    generate_playbook(role_path, target_ip_add)
    ## Append the IP alongside the user/password    
    inventory = f"""{target_ip_add} ansible_connection=ssh ansible_ssh_user=ubuntu ansible_ssh_pass=ubuntu ansible_ssh_extra_args='-o StrictHostKeyChecking=no'"""
    inventory = target_ip_add
    host.exec_run(f'bash -c "echo {inventory} >> /etc/ansible/hosts"')


    ## Add the target's IP address to the inventory
    host.exec_run(f"rm -r {role_path}")

         
    ## This command overwrites the existing ansible test case with our mounted testcase:
    symlink_command = f"ln -s -f /mnt/test {role_path}"

    ## TODO: Why do i need to rm the directory first????
    host.exec_run(f"rm -r {role_path}")
    host.exec_run(symlink_command)
    
    logging.info("Setup of Docker containers complete")

    ## Now setup the environment on the host and target container
    host.exec_run(f"source /mnt/env_setup.sh")
    target.exec_run(f"source /mnt/env_setup.sh")
    
    ## Now Execute tests and capture output
    test_command = "ansible-playbook /mnt/playbook.yml >> /mnt/logs.txt"
    host.exec_run(test_command)
    
    ## Now Nuke the containers
    host.stop()
    target.stop()
    
    ## Copy mnt to output
    output_path = f"output/{role_name}_{perturbation.__name__}{id(perturbation)}"
    os.mkdir(output_path)
    copy_tree("host/mnt", f"{output_path}/mnt")

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
    print(role_paths)
    assert 0
    create_output_folder()

    transformations = [
        ChangeLangTransformation()
    ]

    for role_path in role_paths:
        for transformation in transformations:
            print(f"Testing role: {role_path} with transformation: {transformation.description}")
            run_ansible_role_in_docker(role_path, transformation)
    
    process_output_files()

if __name__ == '__main__':
    main()
