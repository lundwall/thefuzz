from module import BaseModuleTest
import random

class BaseTransformation:

    def __init__(self, description):
        self.description = description

    def transform(self, test: BaseModuleTest):
        """Transform a module test suite."""
        raise NotImplementedError('transform() must be implemented')


class ChangeLangTransformation(BaseTransformation):

    potential_languages = ['fr_FR.UTF-8', 'de_DE.UTF-8', 'es_ES.UTF-8', 'it_IT.UTF-8', 'pt_PT.UTF-8', 'ru_RU.UTF-8']

    def __init__(self):
        super().__init__("Change the language of the executed environment")

    def transform(self, test: BaseModuleTest):
        """Transform a module test suite."""
        test.add_setup_command('export LANG=' + random.choice(self.potential_languages))


class PrependDotSlashTransformation(BaseTransformation):

    def __init__(self, original):
        super().__init__(f"Prepend './' to the filename '{original}'")
        self.original = original

    def transform(self, test: BaseModuleTest):
        """In the code, add './' at the beginning."""
        test.replace_in_code_with(self.original, './' + test.original)


class FilenameTransformation(BaseTransformation):

    def __init__(self, original, new):
        super().__init__(f"Replace '{original}' with '{new}' in filenames, foldernames and code")
        self.original = original
        self.new = new

    def transform(self, test: BaseModuleTest):
        test.replace_in_code_with(self.original, self.new)
        test.replace_in_foldernames_with(self.original, self.new)
        test.replace_in_filenames_with(self.original, self.new)