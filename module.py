import os
import fileinput
import shutil


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

    def set_env_var(self, name: str, value: str) -> None:
        """Set an environment variable at the beginning of the tests"""
        raise NotImplementedError("set_env_var() must be implemented")

    def add_task_before_units(self, task: str) -> None:
        """Add a task before the unit test"""
        """Important: make sure that there is a newline at both the beginning and end of the task"""
        raise NotImplementedError("add_task_before_units() must be implemented")

    def exec_script_before_units(self, script: str) -> None:
        """Add a task before the unit test"""
        raise NotImplementedError("exec_script_before_units() must be implemented")

    def get_exec_command(self) -> str:
        """Get the command to execute the module test"""
        raise NotImplementedError("get_exec_command() must be implemented")


class AnsibleModuleTest(BaseModuleTest):
    """Integration tests for an Ansible module.
    base_path points to the module's test role folder"""

    def __init__(self, base_path):
        super().__init__(
            name=os.path.basename(base_path),
            base_path=base_path,
            code_extension=".yml",
            extra_path="",
            creates_container=False,
        )

    def set_env_var(self, name: str, value: str) -> None:
        """Set an environment variable at the beginning of the tests"""
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        self.add_setup_command(f"export {name}={value}")

    def add_task_before_units(self, task: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        for currentpath, _, files in os.walk(self.copied_path):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)

                    for line in fileinput.input(filepath, inplace=True):
                        if "#" not in line and "- name: " in line:
                            whitespace = len(line) - len(line.lstrip())
                            print(
                                task.replace("\n", "\n" + " " * whitespace)
                                + "\n"
                                + line,
                                end="",
                            )
                        else:
                            print(line, end="")

    def exec_script_before_units(self, script: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        task = f"""
- name: Running {script}
  script: {script}
"""
        self.add_task_before_units(task)

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

    def __init__(self, base_path):
        super().__init__(
            name=os.path.basename(base_path),
            base_path=base_path,
            code_extension=".rb",
            extra_path="spec",
            creates_container=True,
        )

    def _add_manifest_option(self, name: str, value: str):
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
                            and (name not in line)
                        ):  # unit task
                            print(
                                line.replace(f")\n", f", {name}: {value})\n"),
                                end="",
                            )
                        else:
                            print(line, end="")

    def set_env_var(self, name: str, value: str) -> None:
        """Set an environment variable at the beginning of the tests"""
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        self._add_manifest_option("environment", f"{{'{name}' => '{value}'}}")

    def add_task_before_units(self, task: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        """Add a task before the unit test"""
        for currentpath, _, files in os.walk(f"{self.copied_path}/{self.extra_path}"):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)

                    for line in fileinput.input(filepath, inplace=True):
                        if "#" not in line and (
                            " do " in line or " do\n" in line
                        ):  # unit task
                            # Number of spaces before start of line
                            whitespace = len(line) - len(line.lstrip()) + 2
                            # Add indentation since we're now in the 'do' block

                            print(
                                line
                                + task.replace("\n", "\n" + " " * whitespace)
                                + "\n",
                                end="",
                            )
                        else:
                            print(line, end="")

    def exec_script_before_units(self, script: str) -> None:
        if self.copied_path == None:
            raise Exception(f"Module {self.name} must be copied before transformations")
        task = f"""
scp_to(hosts.first, \"/{self.base_path}/files/{script}\", \"/mnt/{script}\")
apply_manifest(\"exec {{ 'Making {script} executable': command => '/usr/bin/chmod +x /mnt/{script}' }}\")
apply_manifest(\"exec {{ 'Running {script}': command => '/mnt/{script}' }}\")
"""
        self.add_task_before_units(task)

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
