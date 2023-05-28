from collections import defaultdict
import os
import subprocess
import shutil, os
from pathlib import Path
import tarfile
import yaml
import glob
import docker
import logging
import pickle

from module import AnsibleModuleTest, BaseModuleTest, PuppetModuleTest
from transformations import (
    BaseTransformation,
    ChangeLangTransformation,
    FilenameTransformation,
    NoTransformation,
    SnapshotTransformation,
)
from collect_state import State


def perturb_tests(module, transformation):
    """
    copy the test directory to a local temporary dir and maybe make changes to it. This temp dir (./mnt/test) Will be mounted to the container at run time and these tests will be performed
    """
    host_directory = "host/mnt/test"
    target_directory = "target/mnt/test"

    # Copy module somewhere where we can modify it
    module.copy_at(host_directory)

    # Prep for snapshots
    SnapshotTransformation().transform(module)

    # Apply the relevant transformation
    transformation.transform(module)

    # Also copy perturbed test to target
    # TODO: Probs unnecessary, we only need the setup + snapshot scripts there
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
    core_base_path = "/modules/ansible/test/integration/targets/"
    core_role_paths = [
        core_base_path + role_path for role_path in config["core_modules"]
    ]
    community_base_path = "/modules/community/tests/integration/targets/"
    community_role_paths = [
        community_base_path + role_path for role_path in config["community_modules"]
    ]
    return core_role_paths + community_role_paths


def generate_playbook(module):
    playbook = f"""
---
- hosts: test_target
  roles:
    - role: '/{module.base_path}'
"""
    with open("host/mnt/playbook.yml", "w") as playbook_file:
        playbook_file.write(playbook)


def create_empty_folder(foldername):
    if os.path.exists(foldername):
        shutil.rmtree(foldername)
    os.makedirs(foldername)


def run_role_in_docker(module: BaseModuleTest, transformation: BaseTransformation):
    # Copies module to host/mnt/test and perturbs it
    perturb_tests(module, transformation)
    generate_playbook(module)

    client = docker.from_env()

    ## First make sure all images are gone:
    for container in client.containers.list():
        if (
            "beaker" in container.attrs["Name"]
            or "testing" in container.attrs["Config"]["Image"]
        ):
            container.kill()
            container.remove()

    ## Setup up the mounting for the tests. We mount a local directory to each of the containers to both provide and collect data for the experiments
    if module.creates_container:  # Puppet setting
        # Give the host container access to the docker socket
        host_mount = [
            docker.types.Mount("/mnt", f"{os.getcwd()}/host/mnt", type="bind"),
            docker.types.Mount("/var/run/docker.sock", "/var/run/docker.sock", "bind"),
        ]
        ## Launch host container
        host = client.containers.run("testing:host", mounts=host_mount, detach=True)
        target = None
    else:  # Ansible setting
        host_mount = [
            docker.types.Mount("/mnt", f"{os.getcwd()}/host/mnt", type="bind"),
        ]
        ## Launch host container
        host = client.containers.run("testing:host", mounts=host_mount, detach=True)
        # Launch target container
        target_mount = [
            docker.types.Mount("/mnt", f"{os.getcwd()}/target/mnt", type="bind"),
        ]
        ## Expose target's port 22 on port 2222 on local PC
        target = client.containers.run(
            "testing:target", ports={"22/tcp": 2222}, mounts=target_mount, detach=True
        )
        ## Add the target container's IP address to the inventory of the host
        inventory = client.containers.get(target.attrs["Id"]).attrs["NetworkSettings"][
            "IPAddress"
        ]
        host.exec_run(f'bash -c "echo {inventory} >> /etc/ansible/hosts"')

    ## TODO: Why do i need to rm the directory first????
    host.exec_run(f"rm -r /{module.base_path}")
    ## This command overwrites the existing test case with our mounted testcase, via a symlink:
    host.exec_run(f"ln -s -f /mnt/test /{module.base_path}")

    ## Now Execute tests and capture output
    test_command = module.get_exec_command()
    output = host.exec_run(test_command)
    ## Dump output
    output_filename = f"host/mnt/logs.txt"
    with open(output_filename, "w") as output_file:
        output_file.write(output.output.decode("utf-8"))

    # Capture target container if necessary to get the script output
    if module.creates_container:
        for container in client.containers.list():
            if "beaker" in container.attrs["Name"]:
                target = container
                # Create a tar archive of the snapshots folder
                with open("target/mnt/snapshots.tar", "wb") as f:
                    bits, _ = target.get_archive("/mnt/snapshots")
                    for chunk in bits:
                        f.write(chunk)
                # Extract the archive folder
                with tarfile.open("target/mnt/snapshots.tar") as t:
                    t.extractall("target/mnt")
                break

    ## Copy mnt to output
    output_path = f"output/{module.name}/{transformation.id}"
    shutil.copytree("host/mnt", f"{output_path}")
    if os.path.exists("target/mnt/snapshots"):
        shutil.copytree("target/mnt/snapshots", f"{output_path}/snapshots")
    else:
        raise Exception("No snapshots were created")

    ## Now Nuke the containers
    host.stop()
    host.remove()
    if target is not None:
        target.stop()
        target.remove()


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
                state: State = pickle.load(
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
                    if (
                        "failed=0" not in output.read()
                        and " 0 failures" not in output.read()
                    ):
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
    create_empty_folder("output")

    transformations = [
        ChangeLangTransformation(),
        FilenameTransformation("test.txt", ".test.txt"),
    ]

    modules = [
        AnsibleModuleTest("modules/ansible/test/integration/targets/lineinfile"),
        AnsibleModuleTest("modules/ansible/test/integration/targets/read_csv"),
        PuppetModuleTest("modules/puppet-archive"),
    ]

    for module in modules:
        # First test with no transformation for baseline
        print(f"Testing role: {module.name} with no transformation")
        run_role_in_docker(module, NoTransformation())
        # Then test with each transformation
        for transformation in transformations:
            print(
                f"Testing role: {module.name} with transformation: {transformation.description}"
            )
            run_role_in_docker(module, transformation)

    process_output_files()


if __name__ == "__main__":
    main()
