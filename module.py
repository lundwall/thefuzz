import os


class BaseModuleTest:
    """Integration tests for a module."""

    def __init__(self, module_name, base_path, code_extension) -> None:
        self.module_name = module_name
        self.base_path = base_path
        self.id = module_name + str(id(self))
        self.code_extension = code_extension

    def add_setup_command(self, command: str) -> None:
        """Execute a shell command at the beginning of the tests"""
        raise NotImplementedError('add_setup_command() must be implemented')

    def replace_in_code_with(self, original: str, replacement: str) -> None:
        """Replace a string in the module tests with another string"""
        raise NotImplementedError('replace_with() must be implemented')

    def replace_in_foldernames_with(self, original: str, replacement: str) -> None:
        """Replace a string in the module tests with another string"""
        raise NotImplementedError('replace_in_foldernames_with() must be implemented')

    def replace_in_filenames_with(self, original: str, replacement: str) -> None:
        """Replace a string in the module tests with another string"""
        raise NotImplementedError('replace_in_filenames_with() must be implemented')


class AnsibleModuleTest(BaseModuleTest):
    """Integration tests for an Ansible module."""

    def __init__(self, module_name, base_path):
        super().__init__(module_name, base_path, '.yml')

    def add_setup_command(self, command: str) -> None:
        """Execute a shell command at the beginning of the tests"""
        with open(os.path.join(self.base_path, 'env_setup.sh'), 'w') as f:
            f.write(command + '\n')

    def replace_in_code_with(self, original: str, replacement: str) -> None:
        for currentpath, _, files in os.walk(self.base_path):
            for filename in files:
                if filename.endswith(self.code_extension):
                    filepath = os.path.join(currentpath, filename)
                    with open(filepath) as f:
                        s = f.read()
                    s = s.replace(original, replacement)
                    with open(filepath, 'w') as f:
                        f.write(s)
    
    def replace_in_filenames_with(self, original: str, replacement: str) -> None:
        for currentpath, _, files in os.walk(self.base_path):
            for filename in files:
                filepath = os.path.join(currentpath, filename)
                filename = os.path.basename(filepath)
                new_filename = filename.replace(original, replacement)
                new_filepath = os.path.join(currentpath, new_filename)
                os.rename(filepath, new_filepath)

    def replace_in_foldernames_with(self, original: str, replacement: str) -> None:
        for currentpath, folders, _ in os.walk(self.base_path):
            for folder in folders:
                folderpath = os.path.join(currentpath, folder)
                foldername = os.path.basename(folderpath)
                new_foldername = foldername.replace(original, replacement)
                new_folderpath = os.path.join(currentpath, new_foldername)
                os.rename(folderpath, new_folderpath)