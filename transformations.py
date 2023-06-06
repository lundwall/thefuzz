from module import BaseModuleTest
import random


def get_random_unicode(length):
    # Update this to include code point ranges to be sampled
    include_ranges = [
        (0x0021, 0x0021),
        (0x0023, 0x0026),
        (0x0028, 0x007E),
        (0x00A1, 0x00AC),
        (0x00AE, 0x00FF),
        (0x0100, 0x017F),
        (0x0180, 0x024F),
        (0x2C60, 0x2C7F),
        (0x16A0, 0x16F0),
        (0x0370, 0x0377),
        (0x037A, 0x037E),
        (0x0384, 0x038A),
        (0x038C, 0x038C),
    ]

    alphabet = [
        chr(code_point)
        for current_range in include_ranges
        for code_point in range(current_range[0], current_range[1] + 1)
    ]
    random_unicode = "".join(random.choice(alphabet) for i in range(length))
    print(random_unicode)
    return random_unicode


# Remove unicode characters that would be problematic in yaml files
def sanitize_unicode(string):
    string = string.replace("/", "")
    string = string.replace("\\", "")
    string = string.replace("\u0000", "")
    string = string.replace(" ", "")
    string = string.replace(":", "")
    string = string.replace("&", "")
    return string


class BaseTransformation:
    def __init__(self, name, description, repeat=False):
        self.name = name
        self.description = description
        self.repeat = repeat

    def transform(self, test: BaseModuleTest):
        """Transform a module test suite."""
        raise NotImplementedError("transform() must be implemented")


class NoTransformation(BaseTransformation):
    def __init__(self):
        super().__init__("no_transformation", "No transformation")

    def transform(self, test: BaseModuleTest):
        """Transform a module test suite."""
        pass


class ChangeLanguage(BaseTransformation):
    potential_languages = {
        "fr": "fr_FR.UTF-8",
        "de": "de_DE.UTF-8",
        "es": "es_ES.UTF-8",
        "it": "it_IT.UTF-8",
        "pt": "pt_PT.UTF-8",
        "ru": "ru_RU.UTF-8",
        "cn": "zh_CN.UTF-8",
    }

    def __init__(self, languages=None, repeat=True):
        super().__init__(
            "change_language",
            "Change the language of the executed environment",
            repeat=repeat,
        )
        self.languages = languages

    def transform(self, test: BaseModuleTest):
        """Transform a module test suite."""
        if self.languages is None:
            selected_lang = random.choice(list(self.potential_languages.values()))
        else:
            selected_lang = self.potential_languages[random.choice(self.languages)]
        test.set_env_var("LC_ALL", selected_lang)


class PrependDotSlash(BaseTransformation):
    def __init__(self, keys):
        super().__init__(
            "prepend_dotslash",
            f"Prepend './' to the filenames of options",
        )
        self.keys = keys

    def transform(self, test: BaseModuleTest):
        """In the code, add './' at the beginning of every filename, used with the given keys."""
        values = test.get_values_of_options(self.keys)
        for value in values:
            filename = value.split("/")[-1]
            new_filename = "./" + filename
            test.replace_in_code_with(filename, new_filename)


class ChangeFilenames(BaseTransformation):
    def __init__(self, keys, repeat=True):
        super().__init__(
            "change_filenames",
            f"Change the option's filename to a random unicode string, everywhere",
            repeat=repeat,
        )
        self.keys = keys

    def transform(self, test: BaseModuleTest):
        values = test.get_values_of_options(self.keys)
        for value in values:
            filename = value.split("/")[-1]
            if "{{" in filename or "}}" in filename or " " in filename:
                continue
            new_filename = get_random_unicode(random.randint(1, 20))
            new_filename = sanitize_unicode(new_filename)
            print(filename, " -> ", new_filename)
            print(value)
            test.replace_in_filenames_with(filename, new_filename)
            test.replace_in_code_with(filename, new_filename)
        breakpoint()


class RemoveRemoteTempDir(BaseTransformation):
    def __init__(self, keys):
        super().__init__(
            "remove_remote_dir",
            f"Create relative paths out of absolute paths",
        )

    def transform(self, test: BaseModuleTest):
        # test.replace_in_filenames_with("{{ remote_tmp_dir }}/", "")
        test.replace_in_code_with("{{ remote_tmp_dir }}/", "")


class ChangeField(BaseTransformation):
    def __init__(self, keys, repeat=True):
        super().__init__(
            "change_field",
            f"Change the field's value to a random unicode string, everywhere",
            repeat=repeat,
        )
        self.keys = keys

    def transform(self, test: BaseModuleTest):
        values = test.get_values_of_options(self.keys)
        for value in values:
            new_value = get_random_unicode(random.randint(1, 60))
            new_value = sanitize_unicode(new_value)
            test.replace_in_code_with(value, new_value)


class CheckIdempotency(BaseTransformation):
    def __init__(self):
        super().__init__(
            "idempotency",
            f"Duplicate all executions of the module's task to check idempotency",
        )

    def transform(self, test: BaseModuleTest):
        test.duplicate_task(test.name)


class DryRunMode(BaseTransformation):
    def __init__(self):
        super().__init__(
            "dry_run",
            f"Add a flag flag to the module's task to run it in dry-run mode",
        )

    def transform(self, test: BaseModuleTest):
        test.set_dry_run_to_task(test.name)


class CaptureSnapshot(BaseTransformation):
    def __init__(self):
        super().__init__("capture_snapshots", f"Collect state before each unit test")

    def transform(self, test: BaseModuleTest):
        test.add_file("collect_state.py")
        test.exec_script_after_task(script="collect_state.py", task_name=test.name)
