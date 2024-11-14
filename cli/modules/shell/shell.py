from modules.api import InstanceAPI, FileSystemAPI, DebugAPI
from modules.shell import commands, parser
from modules.tui import inputs, style
from modules import perms
from modules import fs

from dataclasses import dataclass
import sys


@dataclass
class InstanceData:
    name: str
    id: int
    shell: "ShellSession"
    api: InstanceAPI | None = None 
    fs_api: FileSystemAPI | None = None
    debug_api: DebugAPI | None = None
    
    def __post_init__(self) -> None:
        self.api = InstanceAPI(self.id)
        self.fs_api = FileSystemAPI(self.shell, self.id)
        self.debug_api = DebugAPI(self.id)


class ShellSession:
    def __init__(self, instances: dict[int, str]):
        self.all_instances = instances
        self.instance: InstanceData | None = None
        
        if len(self.all_instances) == 1:
            instance_id = list(self.all_instances.keys())[0]
            instance_name = list(self.all_instances.values())[0]
            self.instance = InstanceData(instance_name, instance_id, self)
            
            print(style.success_msg(f"Selected the only instance: {instance_name}"))
            
        else:
            self.select_instance()
     
        self.raw_perms = self.__load_perms()
        self.perms_type = perms.PermissionType.from_drive_perms(self.raw_perms)
        self.cwd = fs.load_structure(self.instance.fs_api.get_struct())
        
        self._cmds_register = commands.commands_register
        self._cmds_groups = commands.CommandsGroups
     
    def __load_perms(self) -> perms.DrivePermissions:
        permissions = self.instance.api.fetch_perms()
        if permissions is None:
            print(style.error_msg("Failed to fetch instance permissions (API's fault)."))
            sys.exit(1)
            
        return perms.DrivePermissions.from_data(permissions)
        
    def select_instance(self) -> None:
        selected_id = inputs.CheckBox(
            "Select drive instance.",
            self.all_instances
        ).ask()
        
        instance_id = selected_id
        instance_name = self.all_instances[selected_id]
        self.instance = InstanceData(instance_name, instance_id, self)
        
    def update_struct(self) -> None:
        old_cwd = self.cwd.path_to
        
        struct = fs.load_structure(self.instance.fs_api.get_struct())
        self.cwd = struct    
        
        if not struct.move_to(old_cwd):
            print(style.error_msg("Updated files structure does not contain Your current working directory."))
        else:
            self.cwd = self.cwd.move_to(old_cwd)
        
    def mainloop(self) -> None:
        print(style.success_msg("Interactive shell session started...\n\n"))
        
        while True:
            prompt = style.build_shell_prompt(self.instance.name, self.perms_type, self.cwd.path_to)
            
            try:
                query = input(prompt)
                cmd, res_call = parser.parse_query(query, self)

                if not perms.PermissionType.has_perms(self.perms_type, cmd.req_perms):
                    print(style.error_msg(f"This command requires at least {style.colored_type(cmd.req_perms)} permissions!"))
                    continue
                
                res_call()
                
            except KeyboardInterrupt:
                print(style.error_msg("Exiting..."))
                sys.exit(1)
            
            except ValueError as err:
                print(style.query_err_msg(str(err)))

