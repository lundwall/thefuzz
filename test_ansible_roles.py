from collections import defaultdict
import os
import subprocess
import shutil, os
from pathlib import Path
import yaml
import glob
import docker
import logging
import pickle

from module import AnsibleModuleTest
from transformations import (
    ChangeLangTransformation,
    FilenameTransformation,
    NoTransformation,
    SnapshotTransformation,
)
from collect_state import State


def perturb_tests(role_path, perturbation):
    """
    copy the test directory to a local temporary dir and maybe make changes to it. This temp dir (./mnt/test) Will be mounted to the container at run time and these tests will be performed
    """
    # copy subdirectory example
    # Remove the first character of the path, to copy from local repo
    from_directory = role_path[1:]
    host_directory = "host/mnt/test"
    target_directory = "target/mnt/test"
    # Remove centents of temp directory if it already exists
    if os.path.exists(host_directory):
        shutil.rmtree(host_directory)
    shutil.copytree(from_directory, host_directory)

    # Touch the env_setup.sh file
    Path("host/mnt/test/env_setup.sh").touch()

    module_test = AnsibleModuleTest(os.path.basename(role_path), "host/mnt/test")
    perturbation.transform(module_test)

    # Prep for snapshots
    SnapshotTransformation().transform(module_test)

    # Also copy perturbed test to target
    # TODO: Probs unnecessary, we only need the setup script there
    if os.path.exists(target_directory):
        shutil.rmtree(target_directory)
    shutil.copytree(host_directory, target_directory)

    # Remove snapshot directory if it already exists
    if os.path.exists("target/mnt/snapshots"):
        shutil.rmtree("target/mnt/snapshots")

    return


def read_config():
    with open("config.yaml") as config_file:
        config = yaml.load(config_file, Loader=yaml.FullLoader)
    return config


def get_role_paths(config):
    core_base_path = "/ansible/test/integration/targets/"
    core_role_paths = [
        core_base_path + role_path for role_path in config["core_modules"]
    ]
    community_base_path = "/community/tests/integration/targets/"
    community_role_paths = [
        community_base_path + role_path for role_path in config["community_modules"]
    ]
    return core_role_paths + community_role_paths


def generate_playbook(role_path):
    playbook = f"""
---
- hosts: test_target
  roles:
    - role: '{role_path}'
"""
    with open("host/mnt/playbook.yml", "w") as playbook_file:
        playbook_file.write(playbook)


def run_command(command):
    subprocess.run(command, shell=True)


def create_output_folder():
    output_folder = "output"
    if os.path.exists(output_folder):
        shutil.rmtree(output_folder)
    os.makedirs(output_folder)


def run_ansible_role_in_docker(role_path, perturbation):
    perturb_tests(
        role_path, perturbation
    )  # copies module to host/mnt/test and perturbs it
    generate_playbook(role_path)

    role_name = os.path.basename(role_path)

    output_filename = f"host/mnt/logs.txt"
    # Store the transformation in the output file
    with open(output_filename, "w") as output_file:
        output_file.write(perturbation.description + "\n")

    client = docker.from_env()

    ## First make sure all ansible images are gone:
    for container in client.containers.list(
        filters={"ancestor": "ansible:host", "ancestor": "ansible:target"}
    ):
        container.kill()
        container.remove()

    ## Setup up the mounting for the tests. We mount a local directory to each of the containers to both provide and collect data for the experiments
    target_mount = [
        docker.types.Mount("/mnt", f"{os.getcwd()}/target/mnt", type="bind")
    ]
    host_mount = [docker.types.Mount("/mnt", f"{os.getcwd()}/host/mnt", type="bind")]

    ## Launch both containers, the host and the target
    host = client.containers.run("ansible:host", mounts=host_mount, detach=True)

    ## Expose target's port 22 on port 2222 on local PC
    target = client.containers.run(
        "ansible:target", ports={"22/tcp": 2222}, mounts=target_mount, detach=True
    )

    ## Add the target container's IP address to the inventory of the host
    target_ip_add = client.containers.get(target.attrs["Id"]).attrs["NetworkSettings"][
        "IPAddress"
    ]

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

    ## Now Execute tests and capture output
    test_command = 'bash -c "source /mnt/test/env_setup.sh && cd /ansible/test/integration/targets && ansible-playbook /mnt/playbook.yml"'
    ## Dump output
    output = host.exec_run(test_command)
    with open(output_filename, "a") as output_file:
        output_file.write(output.output.decode("utf-8"))

    ## Now Nuke the containers
    host.stop()
    host.remove()
    target.stop()
    target.remove()

    ## Copy mnt to output
    output_path = (
        f"output/{role_name}/{perturbation.__class__.__name__}{id(perturbation)}"
    )
    shutil.copytree("host/mnt", f"{output_path}")
    shutil.copytree("target/mnt/snapshots", f"{output_path}/snapshots")


def process_output_files():
    output_folder = "output"
    output_modules = os.listdir(output_folder)
    no_errors = True
    for output_module in output_modules:
        transformed_states = defaultdict(dict)
        transformations = os.listdir(f"{output_folder}/{output_module}")
        for transformation in transformations:
            # Get all the pickles for this transformation
            all_states = {}
            ps = os.listdir(
                f"{output_folder}/{output_module}/{transformation}/snapshots"
            )
            for p in ps:
                state = pickle.load(
                    open(
                        f"{output_folder}/{output_module}/{transformation}/snapshots/{p}",
                        "rb",
                    )
                )
                # Extract its ID
                state_id = int(p.rstrip(".pkl").lstrip("state_"))
                all_states[state_id] = state
            # Assign to baseline_state or transformed_states accordingly
            if "NoTransformation" in transformation:
                baseline_states = all_states
            else:
                transformed_states[transformation] = all_states
                # Also check logs to see if there were any errors
                with open(
                    f"{output_folder}/{output_module}/{transformation}/logs.txt"
                ) as output:
                    # The executed command is stored in the first line of the output file
                    # Skip new line character at the end
                    transformation = output.readline()[:-1]
                    if "failed=0" not in output.read():
                        no_errors = False
                        print(
                            f"ERROR found in: {output_module}, with transformation: {transformation}"
                        )

        # Now, compare all states for each transformation to the corresponding baseline states
        for transformation, all_states in transformed_states.items():
            num_states = len(all_states)
            if num_states != len(baseline_states):
                num_states = min(num_states, len(baseline_states))
                print(
                    f"Different number of states for: {output_module}, with transformation: {transformation}"
                )
                print(f"Only comparing the first {num_states} states")

            for state_id in range(num_states):
                if baseline_states[state_id] != all_states[state_id]:
                    no_errors = False
                    print(
                        f"STATE DIFFERENCE found in: {output_module} at state: {state_id}, with transformation: {transformation}"
                    )
                    print(f"Baseline state: {baseline_states[state_id].state}")
                    print(f"Transformed state: {all_states[state_id].state}")

    if no_errors:
        print("No errors found :(")


def main():
    config = read_config()
    role_paths = get_role_paths(config)
    create_output_folder()

    transformations = [
        ChangeLangTransformation(),
        FilenameTransformation("test.txt", ".test.txt"),
    ]

    for role_path in role_paths:
        # First test with no transformation for baseline
        print(f"Testing role: {os.path.basename(role_path)} with no transformation")
        run_ansible_role_in_docker(role_path, NoTransformation())
        # Then test with each transformation
        for transformation in transformations:
            print(
                f"Testing role: {os.path.basename(role_path)} with transformation: {transformation.description}"
            )
            run_ansible_role_in_docker(role_path, transformation)

    process_output_files()


if __name__ == "__main__":
    main()
