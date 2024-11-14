from modules import database


@database.DBModel.model("guilds", "!guild_id")
class _GuildPointers:
    guild_id: int
    console_id: int
    logs_id: int
    struct_id: int
    read_role: int
    write_role: int
    admin_role: int
    
    
guilds_ids_db = database.Database[_GuildPointers](_GuildPointers)
    