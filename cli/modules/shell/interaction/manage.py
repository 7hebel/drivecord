from modules.tui import style, list_view
from modules import storage
from modules import perms


from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from modules.shell.shell import ShellSession


def list_members(shell: "ShellSession", params: dict[str, Any]) -> None:
    show_ids = params.get("ShowID")
    
    all_members = shell.instance.api.fetch_members()
    registered = []
    unregistered = []
    
    for member_data in all_members:
        _, _, perm = member_data
        if perm is False:
            unregistered.append(member_data)
        else:
            registered.append(member_data)

    listview = list_view.ListView(f"{shell.instance.name}'s members.")
    
    listview.group(f"Registered: {len(registered)}")
    for (name, id, perm) in registered:
        perm = perms.PermissionType.from_drive_perms(perms.DrivePermissions.from_data(perm))
        perm = style.colored_type(perm)
        
        row = f"{style.tcolor(name, style.PRIMARY)} "
        if show_ids:
            row += f"{style.ITALIC}({id}){style.RESET} "
        row += perm
        
        listview.item(row)  
          
    listview.group(f"Unregistered: {len(unregistered)}")
    for (name, id, _) in unregistered:
        row = f"{style.tcolor(name, style.PRIMARY, styles=[style.AnsiStyle.DIM])} "
        if show_ids:
            row += f"{style.ITALIC}({id}){style.RESET}"
        
        listview.item(row)    

    listview.finish()
    

def manage_perms(shell: "ShellSession", params: dict[str, Any]) -> None:
    member = params.get("member")
    member_as_id = int(member) if member.isnumeric() else None
    permissions_code = params.get("privileges").lower()
    for c in permissions_code:
        if c not in 'awr':
            raise ValueError(f"Invalid privilege indicator: {style.Fore.RED}`{c}`{style.RESET}")
    
    all_members = shell.instance.api.fetch_members()
    for m_data in all_members:
        name, uid, perm = m_data
        if name == member or uid == member_as_id:
            break
    else:
        raise ValueError(f"Member not found: {style.Fore.RED}`{member}`{style.RESET}")
    
    target_perms = perms.DrivePermissions.from_data(perm)
    target_perm_type = perms.PermissionType.from_drive_perms(target_perms)

    if uid == storage.load_user_id():
        raise ValueError("You cannot change your permissions.")

    if target_perm_type == perms.PermissionType.OWNER:
        raise ValueError(f"Member {style.Fore.RED}`{member}`{style.RESET} has {style.colored_type(perms.PermissionType.OWNER)} permissions.")
    
    if target_perm_type == perms.PermissionType.ADMIN and shell.perms_type == perms.PermissionType.ADMIN:
        raise ValueError(f"Member {style.Fore.RED}`{member}`{style.RESET} has {style.colored_type(perms.PermissionType.ADMIN)} permissions. You cannot manage their permissions.")
            
    new_perms_admin = 'a' in permissions_code
    new_perms_write = 'w' in permissions_code
    new_perms_read = 'r' in permissions_code
    
    if new_perms_admin and shell.perms_type == perms.PermissionType.ADMIN:
        raise ValueError(f"Only {style.colored_type(perms.PermissionType.OWNER)} can assign {style.colored_type(perms.PermissionType.ADMIN)} permissions.")
        
    new_perms = perms.DrivePermissions(
        read=new_perms_read, write=new_perms_write, admin=new_perms_admin
    )
    
    shell.instance.api.update_perms(uid, new_perms.export())
    
    