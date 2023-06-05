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
    return "".join(random.choice(alphabet) for i in range(length))


class BaseTransformation:
    def __init__(self, name, description):
        self.name = name
        self.description = description

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
    potential_languages = [
        "fr_FR.UTF-8",
        "de_DE.UTF-8",
        "es_ES.UTF-8",
        "it_IT.UTF-8",
        "pt_PT.UTF-8",
        "ru_RU.UTF-8",
    ]

    def __init__(self):
        super().__init__(
            "change_language", "Change the language of the executed environment"
        )

    def transform(self, test: BaseModuleTest):
        """Transform a module test suite."""
        test.set_env_var("LC_ALL", random.choice(self.potential_languages))


class PrependDotSlash(BaseTransformation):
    def __init__(self, keys):
        super().__init__(
            "prepend_dotslash", f"Prepend './' to the filenames of options"
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
    def __init__(self, keys):
        super().__init__(
            "change_filenames",
            f"Change the option's filename to a random unicode string, everywhere",
        )
        self.keys = keys

    def transform(self, test: BaseModuleTest):
        values = test.get_values_of_options(self.keys)
        for value in values:
            filename = value.split("/")[-1]
            if "{{" in filename or "}}" in filename:
                continue
            new_filename = get_random_unicode(random.randint(1, 60))
            new_filename = new_filename.replace("/", "")
            new_filename = new_filename.replace("\\", "")
            new_filename = new_filename.replace("\u0000", "")
            new_filename = new_filename.replace(" ", "")
            new_filename = new_filename.replace(":", "")
            new_filename = new_filename.replace("&", "")
            print(f"Changing {filename} to {new_filename}")
            test.replace_in_filenames_with(filename, new_filename)
            test.replace_in_code_with(filename, new_filename)


class ChangeField(BaseTransformation):
    def __init__(self, keys):
        super().__init__(
            "change_field",
            f"Change the field's value to a random unicode string, everywhere",
        )
        self.keys = keys

    def transform(self, test: BaseModuleTest):
        values = test.get_values_of_options(self.keys)
        for value in values:
            new_value = get_random_unicode(random.randint(1, 60))
            test.replace_in_code_with(value, new_value)


class CheckIdempotency(BaseTransformation):
    def __init__(self):
        super().__init__(
            "idempotency",
            f"Duplicate all executions of the module's task to check idempotency",
        )

    def transform(self, test: BaseModuleTest):
        test.duplicate_task(test.name)


class CaptureSnapshot(BaseTransformation):
    def __init__(self):
        super().__init__("capture_snapshots", f"Collect state before each unit test")

    def transform(self, test: BaseModuleTest):
        test.add_file("collect_state.py")
        test.exec_script_after_task(script="collect_state.py", task_name=test.name)
