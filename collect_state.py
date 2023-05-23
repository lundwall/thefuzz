import pickle
import os


class State:
    def file_tree(self):
        ##  We do not  check /ansible as this directory should be different in most cases
        return [x for x in os.walk(".") if not x[0].startswith("/ansible")]

    def get_env_variables(self):
        out = ""
        for name, value in os.environ.items():
            out += "{0}: {1}".format(name, value)
        return out

    def __init__(self, state_functions) -> None:
        self.state_functions = state_functions
        self.func_map = {
            "file_tree": self.file_tree,
            "env_variables": self.get_env_variables,
        }
        self.state = {}

    def record_state(self):
        for func in self.state_functions:
            self.state[func] = self.func_map[func]()

    def __eq__(self, obj):
        for key in self.state:
            if self.state[key] != obj.state[key]:
                return False
        return True


if __name__ == "__main__":
    import pprint

    state = State(state_functions=["file_tree", "env_variables"])
    state.record_state()

    if not os.path.exists("/mnt/snapshots"):
        os.makedirs("/mnt/snapshots")

    ## Give file names ascending names
    already_exist = [-1]
    for file in os.listdir("/mnt/snapshots"):
        if file.endswith(".pkl") and file.rstrip(".pkl").lstrip("state_").isnumeric():
            already_exist += [int(file.rstrip(".pkl").lstrip("state_"))]
    already_exist.sort(reverse=True)
    filename = f"state_{str(already_exist[0] + 1)}.pkl"

    with open(f"/mnt/snapshots/{filename}", "wb") as f:
        pickle.dump(state, f)
