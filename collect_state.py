#!/usr/bin/python3

import pickle
import os
import functools
import json
#from termcolor import colored
import hashlib

class State:
    
    ## !!! For downstream compatibility, all functions must return a dict representing the state !!!
    def intersection (self, a, b):
        ## Simple helper method to get intersection of 2 lists
        return [x for x in a if x in b]

    def get_directory_structure(self, rootdir, exclude = []):
        """
        Creates a nested dictionary that represents the folder structure of rootdir
        """
        dir = {}
        if rootdir != "/":
            rootdir = rootdir.rstrip(os.sep)
        start = rootdir.rfind(os.sep) + 1
        for path, dirs, files in os.walk(rootdir):
            if self.intersection(dirs, exclude) != []:
                for ex in self.intersection(dirs, exclude):
                    dirs.remove(ex)
                    
            folders = path[start:].split(os.sep)
            subdir = dict.fromkeys(files)
            parent = functools.reduce(dict.get, folders[:-1], dir)
            parent[folders[-1]] = subdir
        breakpoint()
        return dir
    
    def file_tree(self):
        ##  We do not  check /ansible as this directory should be different in most cases
        return self.get_directory_structure(".", exclude = [
            "ansible",
            #"/mnt"
            "proc",
            "sys",
            'tmp'
        ])
        
    def config_hashes (self):
        '''
            Calculates the hashes of 'all' of the system's config files in /etc
        '''
        # Some files are expected to be different:
        blacklist = [
            ## Every docker container receives a unique hostname, so this must be ignored
            "/etc/hostname",
            "/etc/hosts"  ,
            ## Similarly, the information about mounting is always different:
            "/etc/mtab"          
        ]
        hashes = {}
        for root, dirnames, filenames in os.walk("/etc"):
            for filename in filenames:
                if not filename.endswith(('.lock')):
                    file_path = os.path.join(root, filename)
                    if file_path in blacklist:
                        continue
                    try:
                        hashes[file_path] = hashlib.md5(open(file_path,'rb').read()).hexdigest()
                    except:
                        hashes[file_path] = "Failed to Hash"
        return hashes

    def get_env_variables(self):
        # Hardcoded list of variables that should be ignored
        blacklisted_envs = [
            "SSH_CLIENT",
            "SSH_CONNECTION",
            "LANG",
            "LC_CTYPE"
        ]
        out = {}
        for name, value in os.environ.items():
            if name not in blacklisted_envs:
                out[name] = value
        return out

    def __init__(self, state_functions) -> None:
        self.state_functions = state_functions
        self.func_map = {
            "file_tree": self.file_tree,
            "env_variables": self.get_env_variables,
            "config_hashes": self.config_hashes,
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
    
    def compare (self, other):
        '''
        This allows 2 states to be compared, 
        the result is a list of tuples, 
        each tuple contains the key at which the state differ as well as both states, 
        if no difference, result is empty list
        '''     
        difference = []
        for key in self.state:
            if self.state[key] != other.state[key]:
                difference.append((key, self.state[key],  other.state[key]))
        return difference
    
    ## Mainly for debugging:
    def __str__(self):
        
        out = "-----------START-----------\n"
        
        for key in self.state:
            #out += f"\n\n{colored(key, 'green')}: \n\n"
            out += f"\n\n{key}: \n\n"
            out += json.dumps(self.state[key], indent = 4) + "\n"
        
        out += "-----------END-----------\n"
        
        return out
        


if __name__ == "__main__":
    import pprint

    state = State(state_functions=[
        "file_tree", 
        "env_variables", 
        "config_hashes"
        ])
    #state = State(state_functions=["config_hashes"])
    state.record_state()
    
    print(state)

    
    original_umask = os.umask(0)

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
    
