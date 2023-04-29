import os
import subprocess
import yaml

def read_config():
    with open('config.yaml') as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
    return config

def create_dockerfile(config):
    ansible_core_version = config['core_version']
    ansible_community_version = config['community_version']
    dockerfile = f"""
FROM python:3.10
RUN apt-get update
RUN apt-get -y install locales locales-all
RUN python3 -m pip install https://github.com/ansible/ansible/archive/v{ansible_core_version}.tar.gz
RUN git clone --depth 1 --branch v{ansible_core_version} https://github.com/ansible/ansible /ansible
RUN git clone --depth 1 --branch {ansible_community_version} https://github.com/ansible-collections/community.general.git /community
RUN ansible-galaxy collection install community.general
"""
    with open('Dockerfile', 'w') as dockerfile_file:
        dockerfile_file.write(dockerfile)

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
    with open('playbook.yml', 'w') as playbook_file:
        playbook_file.write(playbook)

def run_command(command):
    subprocess.run(command, shell=True)

def create_output_folder():
    output_folder = 'output'
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

def run_ansible_role_in_docker(role_path, command, command_id):
    generate_playbook(role_path)
    role_name = os.path.basename(os.path.normpath(role_path))
    output_filename = f"output/{role_name}_{command_id}_output.txt"
    # Store the executed command in the output file
    with open(output_filename, 'w') as output_file:
        output_file.write(command)

    docker_command = f"""
docker run --rm -it \
    -v $(pwd)/playbook.yml:/playbook.yml \
    ansible \
    /bin/bash -c "{command} && ansible-playbook /playbook.yml" >> {output_filename}
"""
    run_command(docker_command)

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
    create_dockerfile(config)
    create_output_folder()

    for role_path in role_paths:
        for command_id, command in enumerate(config['perturbation_commands']):
            print(f"Testing role: {role_path} with command: {command}")
            run_ansible_role_in_docker(role_path, command, command_id)
    
    process_output_files()

if __name__ == '__main__':
    main()
