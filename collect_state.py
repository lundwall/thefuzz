import pickle
from state import State
import os


if __name__ == "__main__":
    import pprint
    state = State(state_functions = ["file_tree", "env_variables"])
    state.record_state()

    if not os.path.exists("/mnt/snapshots"):
        os.makedirs("/mnt/snapshots")

    ## Give file names ascending names
    already_exist = [-1]
    for file in os.listdir("/mnt/snapshots"):
        if file.endswith(".pkl") and file.rstrip(".pkl").lstrip("state_").isnumeric():
            already_exist += [int(file.rstrip(".pkl").lstrip("state_"))]
    already_exist.sort(reverse = True)
    filename = f"state_{str(already_exist[0] + 1)}.pkl"
          

    with open (f"/mnt/snapshots/{filename}", "wb") as f:
        pickle.dump(state, f)        