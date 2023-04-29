import os
import subprocess

ROLES = ['lineinfile']
COMMAND = "export LC_ALL=fr_FR.UTF-8 && LANG=fr_FR.UTF-8 && locale"

def get_role_paths():
    base_path = '/ansible/test/integration/targets/'
    role_paths = [base_path + role_path for role_path in ROLES]
    return role_paths

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

def run_ansible_role_in_docker(role_path, command):
    generate_playbook(role_path)
    role_name = os.path.basename(os.path.normpath(role_path))
    output_filename = f"output/{role_name}_output.txt"

    docker_command = f"""
docker run --rm -it \
    -v $(pwd)/playbook.yml:/playbook.yml \
    ansible \
    /bin/bash -c "{command} && ansible-playbook /playbook.yml" > {output_filename}
"""
    run_command(docker_command)

def main():

    role_paths = get_role_paths()
    create_output_folder()

    for role_path in role_paths:
        print(f"Testing role: {role_path}")
        run_ansible_role_in_docker(role_path, COMMAND)
        print(f"Completed testing role: {role_path}")

if __name__ == '__main__':
    main()

