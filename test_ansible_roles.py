from collections import defaultdict
import os
import shutil, os
import tarfile
import yaml
import docker
import pickle
import pathlib
import emoji
from argparse import ArgumentParser

from module import *
from transformations import *
from collect_state import State


MODULE_TYPE_TO_CLASS = {
    "ansible": AnsibleModuleTest,
    "puppet": PuppetModuleTest,
}

TRANSFORMATION_NAME_TO_CLASS = {
    "change_language": ChangeLanguage,
    "prepend_dotslash": PrependDotSlash,
    "change_field": ChangeField,
    "change_filenames": ChangeFilenames,
    "idempotency": CheckIdempotency,
    "remove_remote_dir": RemoveRemoteTempDir,
    "dry_run": DryRunMode,
}

MODULE_UNDER_TEST = ""
TRANSFORMATION_UNDER_TEST = ""
MODULE_BASELINE = ""


def apply_transformation(module, transformation):
    """
    copy the test directory to a local temporary dir and maybe make changes to it. This temp dir (./mnt/test) Will be mounted to the container at run time and these tests will be performed
    """
    host_directory = "host/mnt/test"
    target_directory = "target/mnt/test"

    # Copy module somewhere where we can modify it
    module.copy_at(host_directory)
    shutil.copy("env_setup.sh", f"{module.copied_path}/env_setup.sh")
    # Prep for snapshots
    CaptureSnapshot().transform(module)

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


def get_path_options(source_path: str):
    """
    Returns a list of all the options in the provided source file that are paths
    """
    doc_str = ""
    with open(source_path) as f:
        inside_documentation = False
        for line in f.readlines():
            if line.startswith("DOCUMENTATION = "):
                inside_documentation = True
                continue
            if line == "'''\n" or line == '"""\n':
                break
            if inside_documentation:
                doc_str += line

    documentation = yaml.load(doc_str, Loader=yaml.FullLoader)

    options = documentation["options"]
    path_options = []
    for name, params in options.items():
        if "type" in params:
            if params["type"] == "path":
                path_options.append(name)
    return path_options


def create_config():
    parser = ArgumentParser()
    parser.add_argument("-m", "--modules", nargs="*")
    parser.add_argument("-c", "--config", default="config.yaml")
    parser.add_argument("-n", "--new", action="store_true")
    args = parser.parse_args()

    config_file = args.config
    if not args.new and os.path.exists(config_file):
        print(f"Using the config file at '{config_file}'")
        return config_file

    modules_list = args.modules

    config = {
        "modules": [],
        "general_transformations": [],
    }

    config["general_transformations"].append({"name": "change_language"})

    all_ansible_core_modules = os.listdir("modules/ansible/test/integration/targets")
    all_ansible_community_modules = os.listdir(
        "modules/community/tests/integration/targets"
    )
    all_puppet_modules = os.listdir("modules")
    all_puppet_modules.remove("ansible")
    all_puppet_modules.remove("community")

    for module in modules_list:
        source_path = ""
        if module in all_ansible_core_modules:
            config["modules"].append(
                {
                    "name": module,
                    "type": "ansible",
                    "path": f"modules/ansible/test/integration/targets/{module}",
                    "transformations": [],
                }
            )
            source_path = f"modules/ansible/lib/ansible/modules/{module}.py"
        elif module in all_ansible_community_modules:
            config["modules"].append(
                {
                    "name": module,
                    "type": "ansible",
                    "path": f"modules/community/tests/integration/targets/{module}",
                    "transformations": [],
                }
            )
            source_path = f"modules/community/plugins/modules/{module}.py"
        elif module in all_puppet_modules:
            config["modules"].append(
                {
                    "name": module.lstrip("puppet-"),
                    "type": "puppet",
                    "path": f"modules/{module}",
                    "transformations": [],
                }
            )
        else:
            raise Exception("Sorry, this module cannot be found")

        # Add all filename transformations if there is relevant documentation
        if source_path != "":
            path_options = get_path_options(source_path)
            if len(path_options) > 0:
                config["modules"][-1]["transformations"].append(
                    {
                        "name": "change_filenames",
                        "options": {"keys": path_options},
                    }
                )
                config["modules"][-1]["transformations"].append(
                    {
                        "name": "prepend_dotslash",
                        "options": {"keys": path_options},
                    }
                )

    # Output this config dict to a yaml file
    with open(config_file, "w") as config_f:
        yaml.Dumper.ignore_aliases = lambda *args: True
        yaml.dump(config, config_f, default_flow_style=False)

    input(
        f"""Created a sample configuration file at '{config_file}'.
Modify it if necessary and press Enter to continue.
"""
    )

    return config_file


def read_config(config_file):
    with open(config_file) as config_f:
        config = yaml.load(config_f, Loader=yaml.FullLoader)
    return config


def transformations_per_module(config):
    mod_trans = {}
    for module_data in config["modules"]:
        module = MODULE_TYPE_TO_CLASS[module_data["type"]](
            name=module_data["name"], base_path=module_data["path"]
        )
        mod_trans[module] = [NoTransformation()]
        # Start with baseline test without transformation
        # Add all general transformations
        # First, clean up: make sure the transformation lists exist, empty if necessary
        if (
            "general_transformations" not in config
            or config["general_transformations"] == None
        ):
            config["general_transformations"] = []
        if (
            "transformations" not in module_data
            or module_data["transformations"] == None
        ):
            module_data["transformations"] = []

        for transformation_data in (
            config["general_transformations"] + module_data["transformations"]
        ):
            if (
                "options" not in transformation_data
                or transformation_data["options"] == None
            ):
                transformation = TRANSFORMATION_NAME_TO_CLASS[
                    transformation_data["name"]
                ]()
            else:
                transformation = TRANSFORMATION_NAME_TO_CLASS[
                    transformation_data["name"]
                ](**transformation_data["options"])
            mod_trans[module].append(transformation)
    return mod_trans


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
    apply_transformation(module, transformation)
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

    env = {"REPRODUCE": os.getenv("REPRODUCE")}
    if module.creates_container:  # Puppet setting
        # Give the host container access to the docker socket
        host_mount = [
            docker.types.Mount("/mnt", f"{os.getcwd()}/host/mnt", type="bind"),
            docker.types.Mount("/var/run/docker.sock", "/var/run/docker.sock", "bind"),
        ]
        ## Launch host container
        host = client.containers.run(
            "testing:host", mounts=host_mount, detach=True, environment=env
        )
        target = None
    else:  # Ansible setting
        host_mount = [
            docker.types.Mount("/mnt", f"{os.getcwd()}/host/mnt", type="bind"),
        ]
        ## Launch host container
        host = client.containers.run(
            "testing:host", mounts=host_mount, detach=True, environment=env
        )
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

    # breakpoint()
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

    ## Now process output, if the run was a baseline run, save the output, else, compare to baseline results
    baseline_run = transformation.name == "no_transformation"

    if baseline_run:
        ## Save output to a special folder
        global MODULE_BASELINE
        MODULE_BASELINE = grab_states()
        output_path = f"output/{module.name}/baseline"
        if os.path.exists(output_path):
            shutil.rmtree(output_path)

        # pathlib.Path(output_path).mkdir(parents=True, exist_ok=True)

        shutil.copytree("host/mnt", f"{output_path}")
        if os.path.exists("target/mnt/snapshots"):
            shutil.copytree("target/mnt/snapshots", f"{output_path}/snapshots")
        else:
            raise Exception("No snapshots were created")
    else:
        ## Check output, if either a crash occurs or if the output state differs to the baseline, we save the output, else we do not
        try:
            crashed = detect_crashes()

            ## Calculate output path if we detected an error
            t_id = 0
            if os.path.exists(f"output/{module.name}"):
                all_equal_ts = [
                    int(t.lstrip(transformation.name))
                    for t in os.listdir(f"output/{module.name}")
                    if t.startswith(transformation.name)
                ]
                if len(all_equal_ts) > 0:
                    t_id = max(all_equal_ts) + 1
            output_path = f"output/{module.name}/{transformation.name}{t_id:09d}"
            no_error = True

            if crashed:
                print(
                    emoji.emojize("🧐"),
                    "detected an abmnormal exit of the test suite, saving logs to output: ",
                    output_path,
                )
                shutil.copytree("host/mnt", f"{output_path}")
                no_error = False

            state_differences = compare_to_baseline()
            if state_differences != []:
                ## Copy mnt to output
                # First, get latest id
                print(
                    emoji.emojize("🧐"),
                    "detected an difference between states of the baseline test suite and out modifications, saving intermediate states to output: ",
                    output_path,
                )
                if os.path.exists("target/mnt/snapshots"):
                    shutil.copytree("target/mnt/snapshots", f"{output_path}/snapshots")
                else:
                    raise Exception("No snapshots were created")
                no_error = False
            if no_error:
                print(emoji.emojize("😃"), " Nothing Detected")

        except Exception as e:
            print("Evaluation Failed")
            print(e)

    ## Now Nuke the containers
    host.stop()
    host.remove()
    if target is not None:
        target.stop()
        target.remove()


def detect_crashes():
    with open(f"host/mnt/logs.txt") as output:
        if "failed=0" not in output.read() and " 0 failures" not in output.read():
            print(
                f"ERROR found in: {MODULE_UNDER_TEST}, with transformation: {TRANSFORMATION_UNDER_TEST}"
            )
            return True
    return False


def compare_to_baseline():
    """
    Compares the states in target/mnt after running tests to the baseline states
    """

    current_states = grab_states()
    num_states = len(current_states)

    difference = []
    if num_states != len(MODULE_BASELINE):
        num_states = min(num_states, len(MODULE_BASELINE))
        print(
            f"Different number of states for: {MODULE_UNDER_TEST}, with transformation: {TRANSFORMATION_UNDER_TEST}"
        )
        print(f"Only comparing the first {num_states} states")

    for state_id in range(num_states):
        if MODULE_BASELINE[state_id] != current_states[state_id]:
            no_errors = False
            print(
                f"STATE DIFFERENCE found in: {MODULE_UNDER_TEST} at state: {state_id}, with transformation: {TRANSFORMATION_UNDER_TEST}"
            )
            print(f"Baseline state: {MODULE_BASELINE[state_id].state}")
            print(f"Transformed state: {current_states[state_id].state}")

            difference.append(
                [
                    state_id,
                    MODULE_BASELINE[state_id].state,
                    current_states[state_id].state,
                ]
            )
    return difference


def grab_states():
    if not os.path.exists("target/mnt/snapshots"):
        raise Exception("No snapshots were created")
    all_states = {}
    ps = os.listdir(f"target/mnt/snapshots")
    for p in ps:
        state: State = pickle.load(
            open(
                f"target/mnt/snapshots/{p}",
                "rb",
            )
        )
        # Extract its ID
        state_id = int(p.rstrip(".pkl").lstrip("state_"))
        all_states[state_id] = state
    return all_states


def main():
    create_empty_folder("output")

    config_path = create_config()
    config = read_config(config_path)

    global MODULE_UNDER_TEST
    global TRANSFORMATION_UNDER_TEST

    module_trans = transformations_per_module(config)
    # First, get baseline runs for each module
    for module in module_trans.keys():
        MODULE_UNDER_TEST = module.name
        transformation = NoTransformation()
        TRANSFORMATION_UNDER_TEST = transformation.name
        print(f"Testing role: {module.name} with no transformation")
        run_role_in_docker(module, transformation)
    # Then, run random transformations for random modules
    while len(module_trans) > 0:
        module = random.choice(list(module_trans.keys()))
        MODULE_UNDER_TEST = module.name
        transformation = random.choice(module_trans[module])
        TRANSFORMATION_UNDER_TEST = transformation.name
        print(
            f"Testing role: {module.name} with transformation: {transformation.description}"
        )
        run_role_in_docker(module, transformation)
        if not transformation.repeat:
            module_trans[module].remove(transformation)
            if len(module_trans[module]) == 0:
                del module_trans[module]


if __name__ == "__main__":
    main()
