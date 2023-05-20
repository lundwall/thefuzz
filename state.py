class SystemState ():
    
    def __init__(self) -> None:
        self.file_tree = None
        self.port_state = None
        self.running_processes = None
        self.running_programs = None
        self.running_services = None
        self.users = None
        self.permissions = None
        self.set_env_variables = None ## Blacklist fucked with envs
        
        
        
        