import os
import fileinput
import shutil
import sys
import re


class BaseModuleTest:
    """Integration tests for a module."""

    def __init__(
        self, name, base_path, code_extension, extra_path, creates_container
    ) -> None:
        self.name = name
        self.base_path = base_path
        # copied_path is where the copied module will be mutated
        # Important: to use after calling copy_at()
        self.copied_path = None
        self.id = name + str(id(self))
        self.code_extension = code_extension
        self.creates_container = creates_container
        self.extra_path = extra_path

    def copy_at(self, copied_path: str):
        """Duplicate the module test at a new path"""
        self.copied_path = copied_path

        if os.path.exists(self.copied_path):
            shutil.rmtree(self.copied_path)
        shutil.copytree(self.base_path, self.copied_path)

    def add_setup_command(self, command: str) -> None:
        """
        Execute a shell command at the beginning of the tests
        This will be executed on the host container only
        On Ansible, the host environment is copied over to the target container
        This is not the case for Puppet, so if we want to change environment variable,
        we should use the explicit set_env_var() method
        """
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        with open(f"{self.copied_path}/env_setup.sh", "a") as f:
            f.write(command + "\n")
        os.chmod(f"{self.copied_path}/env_setup.sh", 0o777)

    def replace_in_code_with(self, original: str, replacement: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        for currentpath, _, files in os.walk(f"{self.copied_path}/{self.extra_path}"):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)
                    with open(filepath) as f:
                        s = f.read()
                    s = s.replace(original, replacement)
                    with open(filepath, "w") as f:
                        f.write(s)

    def replace_in_filenames_with(
        self, original: str, replacement: str, exclude_folders=False
    ) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        for currentpath, folders, files in os.walk(
            f"{self.copied_path}/{self.extra_path}"
        ):
            renamable = files if exclude_folders else folders + files
            for filename in renamable:
                filepath = os.path.join(currentpath, filename)
                filename = os.path.basename(filepath)
                new_filename = filename.replace(original, replacement)
                new_filepath = os.path.join(currentpath, new_filename)
                os.rename(filepath, new_filepath)

    def add_file(self, filepath: str) -> None:
        """Add a file to the module test's 'copied_path/files' folder"""
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        new_filepath = os.path.join(
            self.copied_path, "files", os.path.basename(filepath)
        )
        os.makedirs(os.path.dirname(new_filepath), exist_ok=True)
        shutil.copyfile(filepath, new_filepath)

    def add_option_to_task(self, task_name, key, value) -> None:
        """Add an option to a task"""
        raise NotImplementedError("add_option_to_task() must be implemented")

    def set_env_var(self, name: str, value: str) -> None:
        """Set an environment variable at the beginning of the tests"""
        raise NotImplementedError("set_env_var() must be implemented")

    def get_values_of_options(self, options) -> list:
        """Get the values of an option"""
        raise NotImplementedError("get_values_of_options() must be implemented")

    def add_after_task(self, task: str, existing_task_name: str) -> None:
        """Add a task after the unit test"""
        """Important: make sure that there is a newline at both the beginning and end of the task"""
        raise NotImplementedError("add_after_task() must be implemented")

    def exec_script_after_task(self, script: str, task_name: str) -> None:
        """Add a task before the unit test"""
        raise NotImplementedError("exec_script_after_task() must be implemented")

    def duplicate_task(self, task_name: str) -> None:
        """Copy a task and paste it right after"""
        raise NotImplementedError("duplicate_task() must be implemented")

    def get_exec_command(self) -> str:
        """Get the command to execute the module test"""
        raise NotImplementedError("get_exec_command() must be implemented")


class AnsibleModuleTest(BaseModuleTest):
    """Integration tests for an Ansible module.
    base_path points to the module's test role folder"""

    def __init__(self, name, base_path):
        super().__init__(
            name=name,
            base_path=base_path,
            code_extension=".yml",
            extra_path="",
            creates_container=False,
        )

    def add_option_to_task(self, task_name, key, value) -> None:
        option = f"""
  {key}: {value}
"""
        self.add_after_task(option, task_name)

    def set_env_var(self, name: str, value: str) -> None:
        """Set an environment variable at the beginning of the tests"""
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        self.add_setup_command(f"export {name}={value}")

    def get_values_of_options(self, keys) -> list:
        values = []
        for currentpath, _, files in os.walk(self.copied_path):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)
                    inside_task = False
                    task_indentation = 0
                    for line in fileinput.input(filepath, inplace=True):
                        if not line.lstrip().startswith("#") and line != "\n":
                            if not inside_task:
                                if line.lstrip().startswith(f"{self.name}:"):
                                    inside_task = True
                                    task_indentation = len(line) - len(line.lstrip())
                            else:
                                if len(line) - len(line.lstrip()) <= task_indentation:
                                    if line.lstrip().startswith(f"{self.name}:"):
                                        task_indentation = len(line) - len(
                                            line.lstrip()
                                        )
                                    else:
                                        inside_task = False
                                else:
                                    for k in keys:
                                        if line.lstrip().startswith(f"{k}:"):
                                            values.append(
                                                line.lstrip()
                                                .lstrip(f"{k}:")
                                                .lstrip()
                                                .rstrip("\n")
                                                .lstrip('"')
                                                .lstrip("'")
                                                .rstrip('"')
                                                .rstrip("'")
                                            )
                                        break

                        print(line, end="")
        values = list(set(values))
        return values

    def add_after_task(self, task: str, existing_task_name: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        for currentpath, _, files in os.walk(self.copied_path):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)

                    inside_name = False
                    name_indentation = 0
                    task_in_name = False
                    for line in fileinput.input(filepath, inplace=True):
                        if not line.lstrip().startswith("#") and line != "\n":
                            if not inside_name:
                                if line.lstrip().startswith("- name: "):
                                    inside_name = True
                                    task_in_name = False
                                    name_indentation = len(line) - len(line.lstrip())
                            else:
                                if len(line) - len(line.lstrip()) <= name_indentation:
                                    if task_in_name:
                                        print(
                                            task.replace(
                                                "\n",
                                                "\n" + " " * name_indentation,
                                            )
                                            + "\n",
                                            end="",
                                        )
                                    if line.lstrip().startswith("- name: "):
                                        task_in_name = False
                                        name_indentation = len(line) - len(
                                            line.lstrip()
                                        )
                                    else:
                                        inside_name = False
                                elif line.lstrip() == f"{existing_task_name}:\n":
                                    task_in_name = True

                        print(line, end="")
                    # File ends with the task
                    if inside_name and task_in_name:
                        with open(filepath, "a") as f:
                            f.write(
                                task.replace("\n", "\n" + " " * name_indentation) + "\n"
                            )

    def exec_script_after_task(self, script: str, task_name: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        task = f"""
- name: Create snapshot
  script: {script}
"""
        self.add_after_task(task=task, existing_task_name=task_name)

    def duplicate_task(self, task_name) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        for currentpath, _, files in os.walk(self.copied_path):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)

                    entire_name = ""
                    inside_name = False
                    name_indentation = 0
                    task_in_name = False
                    for line in fileinput.input(filepath, inplace=True):
                        if not line.lstrip().startswith("#") and line != "\n":
                            if not inside_name:
                                if line.lstrip().startswith("- name: "):
                                    inside_name = True
                                    name_indentation = len(line) - len(line.lstrip())
                                    entire_name = line
                            else:
                                if len(line) - len(line.lstrip()) <= name_indentation:
                                    if task_in_name:
                                        print(entire_name, end="")
                                    if line.lstrip().startswith("- name: "):
                                        task_in_name = False
                                        name_indentation = len(line) - len(
                                            line.lstrip()
                                        )
                                        entire_name = ""
                                elif line.lstrip() == f"{task_name}:\n":
                                    task_in_name = True
                                entire_name += line
                        print(line, end="")
                    # File ends with the task
                    if inside_name:
                        with open(filepath, "a") as f:
                            f.write("\n" + entire_name)

    def get_exec_command(self) -> str:
        """Get the command to execute the module test on Docker"""
        test_command = 'bash -c "'
        # If setup_env.sh exists, source it
        if os.path.exists(f"{self.copied_path}/env_setup.sh"):
            test_command += f"source /{self.base_path}/env_setup.sh && "
        test_command += 'cd /modules/ansible/test/integration/targets && ansible-playbook /mnt/playbook.yml"'

        return test_command


class PuppetModuleTest(BaseModuleTest):
    """Integration tests for a Puppet module.
    base_path points to the module's 'spec' folder"""

    def __init__(self, name, base_path):
        super().__init__(
            name=name,
            base_path=base_path,
            code_extension=".rb",
            extra_path="spec",
            creates_container=True,
        )

    def add_option_to_task(self, task_name: str, key: str, value: str):
        # apply_manifest's signature is: apply_manifest(manifest, opts = {}, &block) ⇒ Object
        # Here, we want to add an option to the opts hash
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        """Add a task before the unit test"""
        for currentpath, _, files in os.walk(f"{self.copied_path}/{self.extra_path}"):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)

                    for line in fileinput.input(filepath, inplace=True):
                        # Not a comment, and the whole function call is on one line
                        # Also, if the option is already set, bail
                        if (
                            "#" not in line
                            and (
                                "apply_manifest(" in line
                                or "apply_manifest_on(" in line
                            )
                            and (")\n" in line)
                            and (key not in line)
                        ):  # unit task
                            print(
                                line.replace(f")\n", f", {key}: {value})\n"),
                                end="",
                            )
                        else:
                            print(line, end="")

    def set_env_var(self, name: str, value: str) -> None:
        """Set an environment variable at the beginning of the tests"""
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        self.add_option_to_task("", "environment", f"{{'{name}' => '{value}'}}")

    def get_values_of_options(self, options) -> list:
        """Get the values of an option"""
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        """Add a task after the unit test"""
        values = []
        for currentpath, _, files in os.walk(f"{self.copied_path}/{self.extra_path}"):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)

                    inside_task = False
                    task_indentation = 0
                    for line in fileinput.input(filepath, inplace=True):
                        if "#" not in line and "collect_state.py" not in line:
                            if not inside_task and line.lstrip().startswith(
                                f"{self.name} {{"
                            ):
                                inside_task = True
                                task_indentation = len(line) - len(line.lstrip())
                            elif (
                                inside_task
                                and len(line) - len(line.lstrip()) <= task_indentation
                            ):
                                inside_task = False

                            if inside_task or "apply_manifest" in line:
                                for o in options:
                                    values += re.findall(
                                        f"{o} {{ ['\"](.*?)['\"]:", line
                                    )
                                    values += re.findall(
                                        f"{o} =>[ ]*['\"](.*?)['\"]", line
                                    )

                        print(line, end="")
        return values

    def add_after_task(self, task: str, existing_task_name: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        """Add a task after the unit test"""
        for currentpath, _, files in os.walk(f"{self.copied_path}/{self.extra_path}"):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)

                    for line in fileinput.input(filepath, inplace=True):
                        if (
                            "#" not in line
                            and (
                                "apply_manifest(" in line
                                or "apply_manifest_on(" in line
                            )
                            and (")\n" in line)
                            and "collect_state.py" not in line
                        ):  # unit task
                            # Number of spaces before start of line
                            task_indentation = len(line) - len(line.lstrip())
                            # Add indentation since we're now in the 'do' block

                            print(
                                line
                                + task.replace("\n", "\n" + " " * task_indentation)
                                + "\n",
                                end="",
                            )
                        else:
                            print(line, end="")

    def exec_script_after_task(self, script: str, task_name: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        task = f"""
scp_to(hosts.first, \"/{self.base_path}/files/{script}\", \"/mnt/{script}\")
apply_manifest(\"exec {{ 'Making {script} executable': command => '/usr/bin/chmod +x /mnt/{script}' }}\")
apply_manifest(\"exec {{ 'Running {script}': command => '/mnt/{script}' }}\")
"""
        self.add_after_task(task, task_name)

    def duplicate_task(self, task_name) -> None:
        """
        Hard to say if a apply_manifest() call is a task or not, so we ignore task_name
        and duplicate all apply_manifest() calls. Most of those will be our tested module,
        but in any case, puppet manifests should always be idempotent.
        """
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        for currentpath, _, files in os.walk(self.copied_path):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)
                    for line in fileinput.input(filepath, inplace=True):
                        if (
                            "#" not in line
                            and (
                                "apply_manifest(" in line
                                or "apply_manifest_on(" in line
                            )
                            and (")\n" in line)
                            and (
                                "collect_state.py" not in line
                            )  # Make sure we're not duplicating any snapshots
                        ):  # unit task
                            print(line, end="")
                        print(line, end="")

    def get_exec_command(self) -> str:
        """Get the command to execute the module test"""
        test_command = 'bash -c "'
        # If setup_env.sh exists, source it
        if os.path.exists(f"{self.copied_path}/env_setup.sh"):
            test_command += f"source /{self.base_path}/env_setup.sh && "
        test_command += f"cd /{self.base_path}"
        test_command += " && PDK_DISABLE_ANALYTICS=true pdk bundle install"
        test_command += ' && BEAKER_destroy=no BEAKER_setfile=ubuntu2204-64 DOCKER_IN_DOCKER=true pdk bundle exec rspec spec/acceptance"'

        return test_command
