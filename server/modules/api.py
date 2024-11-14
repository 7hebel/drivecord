from modules.discord.data import DriveGuild, fs
from modules.discord.client import client
from modules.paths import sizeof_fmt
from modules.logs import Log
from modules import accounts
from modules import schemas
from modules import errors
from modules import perms

from fastapi.responses import JSONResponse, Response, PlainTextResponse
from typing import Union, Tuple, TypeVar, Any, Coroutine
from fastapi.middleware.cors import CORSMiddleware
from collections.abc import Callable
from fastapi import FastAPI, Request
from discord import Guild, Message
from http import HTTPStatus
import asyncio
import json


R = TypeVar("R")

def run_async(async_fn: Callable[[Any], Coroutine[Any, Any, R]]) -> R:
    return asyncio.run_coroutine_threadsafe(async_fn, client.loop).result()

def rich_error_response(err_msg: str) -> PlainTextResponse:
    return PlainTextResponse(err_msg, HTTPStatus.CONFLICT)


AUTH_VALIDATION_FAIL = Response(status_code=HTTPStatus.UNAUTHORIZED)

def validate_auth(data: schemas.Auth, request: Request) -> bool:
    user = accounts.User.get_by_uid(data.uid)
    if user is None:
        Log.warn(f"Auth failed: {data.uid} user not found.")
        return False

    if not user.check_access_token(data.token, request.client.host):
        Log.warn(f"Auth failed: {data.uid} ({data.token}) invalid token for ip: {request.client.host}")
        return False

    return True


async def prepare_restricted_endpoint_data(
        instance_id: int, data: schemas.Auth, request: Request
    ) -> Union[
        Tuple[bool, Response],
        Tuple[bool, Tuple[accounts.User, Guild, DriveGuild]]
    ]:
    if not validate_auth(data, request):
        return (False, AUTH_VALIDATION_FAIL)

    user = accounts.User.get_by_uid(data.uid)
    if instance_id not in user.servers_ids:
        Log.warn(f"Client {data.uid} tried to operate on foreign instance: {instance_id}")
        return (False, Response(status_code=HTTPStatus.FORBIDDEN))

    guild = client.get_guild(instance_id)
    if guild is None:
        Log.warn(f"Client {data.uid} tried to operate on not existing instance: {instance_id}")
        return (False, Response(status_code=HTTPStatus.NOT_IMPLEMENTED))
    
    drive_manager = await DriveGuild.get(guild)
    return (True, (user, guild, drive_manager))
    

api = FastAPI()
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.get("/api/")
async def check_status() -> Response:
    return Response(status_code=HTTPStatus.OK)


ACCESS_API = "/api/access/"

@api.get(ACCESS_API + "validateToken/{uid}/{token}")
async def validate_token(uid: int, token: str, request: Request) -> Response:
    user = accounts.User.get_by_uid(uid)
    if user is None:
        return Response(status_code=HTTPStatus.NOT_FOUND)

    if not user.check_access_token(token, request.client.host):
        return Response(status_code=HTTPStatus.UNAUTHORIZED)

    return Response(status_code=HTTPStatus.OK)

@api.get(ACCESS_API + "validateUID/{uid}")
async def validate_uid(uid: int, request: Request) -> Response:
    user = accounts.User.get_by_uid(uid)
    if user is None:
        return Response(status_code=HTTPStatus.NOT_FOUND)

    return Response(status_code=HTTPStatus.OK)

@api.post(ACCESS_API + "login")
async def login(data: schemas.AccountLogin, request: Request) -> Response:
    user = accounts.User.get_by_uid(data.uid)
    if user is None:
        return Response(status_code=HTTPStatus.NOT_FOUND)

    if user.check_password(data.password):
        return Response(status_code=HTTPStatus.OK)

    return Response(status_code=HTTPStatus.UNAUTHORIZED)

@api.post(ACCESS_API + "logout")
async def logout(data: schemas.Auth, request: Request) -> Response:
    user = accounts.User.get_by_uid(data.uid)
    if user is None:
        return Response(status_code=HTTPStatus.NOT_FOUND)
    
    if not user.check_access_token(data.token, request.client.host):
        return Response(status_code=HTTPStatus.UNAUTHORIZED)
    
    user.burn_access_token(data.token)
    return Response(status_code=HTTPStatus.OK)
    
@api.post(ACCESS_API + "getToken")
async def get_token(data: schemas.GetToken, request: Request) -> Response:
    user = accounts.User.get_by_uid(data.uid)
    if user is None:
        return Response(status_code=HTTPStatus.NOT_FOUND)

    token = user.request_access_token(data.password, request.client.host)
    if isinstance(token, errors.T_Error):
        if token == errors.INVALID_PASSWORD:
            return Response(status_code=HTTPStatus.UNAUTHORIZED)

        if token == errors.MAX_ACCESS_TOKENS:
            return Response(status_code=HTTPStatus.NOT_ACCEPTABLE)

    return PlainTextResponse(content=token.token_id, status_code=HTTPStatus.OK)


INSTANCE_API = "/api/instance/"

@api.post(INSTANCE_API + "fetchAll")
async def load_instances(data: schemas.Auth, request: Request) -> JSONResponse:
    if not validate_auth(data, request):
        return AUTH_VALIDATION_FAIL

    user = accounts.User.get_by_uid(data.uid)
    instances = user.get_instances()
    return JSONResponse(instances)

@api.post(INSTANCE_API + "{instance_id}/getPerms")
async def get_user_perms(instance_id: int, data: schemas.Auth, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, _, drive_manager = response

    perms = drive_manager.get_permissions(data.uid).export()
    return JSONResponse(perms)

@api.post(INSTANCE_API + "{instance_id}/fetchMembers")
async def get_members(instance_id: int, data: schemas.Auth, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, guild, drive_manager = response
    all_members = []

    for g_member in guild.members:
        if g_member.bot:
            continue
        
        account = accounts.User.get_by_uid(g_member.id)
        if account is None:
            all_members.append([g_member.name, g_member.id, False])
            continue
        
        all_members.append([g_member.name, g_member.id, drive_manager.get_permissions(g_member).export()])

    return JSONResponse(all_members)

@api.post(INSTANCE_API + "{instance_id}/updatePerms")
async def update_perms(instance_id: int, data: schemas.UpdatePerms, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    user, guild, drive_manager = response
    
    user_perms = drive_manager.get_permissions(user.discord_id)
    if not user_perms.admin and not user_perms.owner:
        Log.warn(f"Client {data.uid} tried to update perms for user without Admin or Owner perms")
        return Response(status_code=HTTPStatus.FORBIDDEN)
    
    target = accounts.User.get_by_uid(data.member_id)
    if target is None:
        Log.warn(f"Client {data.uid} tried to update permissions for invalid user: {data.member_id}")
        return Response(status_code=HTTPStatus.NOT_FOUND)

    target_member = guild.get_member(target.discord_id)
    if target_member is None:
        Log.warn(f"Client {data.uid} tried to update permissions for invalid user: {data.member_id} (not on server)")
        return Response(status_code=HTTPStatus.NOT_FOUND)
    
    new_perms = perms.DrivePermissions.import_data(data.perms)
    if not user_perms.owner and new_perms.admin:
        Log.warn(f"Client {data.uid} tried to assign Admin perms to user: {data.member_id} without Owner perms.")
        return Response(status_code=HTTPStatus.FORBIDDEN)
    

    run_async(drive_manager.set_permissions(target_member, new_perms))
    
    return Response(status_code=HTTPStatus.OK)


FS_API = "/api/fs/"

@api.post(FS_API + "{instance_id}/structure")
async def fetch_structure(instance_id: int, data: schemas.Auth, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, _, drive_manager = response

    struct_base_dir = run_async(drive_manager.get_struct())
    struct = struct_base_dir.api_export()
    
    return JSONResponse(struct, HTTPStatus.OK)

@api.post(FS_API + "{instance_id}/mkfile")
async def make_file(instance_id: int, data: schemas.Path, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    user, _, drive_manager = response
    end_path = data.cwd + data.path 
    
    status = run_async(drive_manager.create_file(user.discord_id, end_path))
    if isinstance(status, errors.T_Error):
        return rich_error_response(status)
    
    return Response(status_code=HTTPStatus.OK)

@api.post(FS_API + "{instance_id}/mkdir")
async def make_dir(instance_id: int, data: schemas.Path, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    user, _, drive_manager = response
    end_path = data.cwd + data.path 
    
    status = run_async(drive_manager.create_directory(user.discord_id, end_path))
    if isinstance(status, errors.T_Error):
        return rich_error_response(status)
    
    return Response(status_code=HTTPStatus.OK)

@api.post(FS_API + "{instance_id}/rm")
async def rm_obj(instance_id: int, data: schemas.Path, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    user, _, drive_manager = response
    end_path = data.cwd + data.path 
    
    status = run_async(drive_manager.delete_fs_obj(user.discord_id, end_path))
    if isinstance(status, errors.T_Error):
        return rich_error_response(status)
    
    return Response(status_code=HTTPStatus.OK)
    
@api.post(FS_API + "{instance_id}/rename")
async def rename_obj(instance_id: int, data: schemas.Rename, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    user, _, drive_manager = response
    end_path = data.cwd + data.path 
    
    status = run_async(drive_manager.rename(user.discord_id, end_path, data.new_name))
    if isinstance(status, errors.T_Error):
        return rich_error_response(status)
    
    return Response(status_code=HTTPStatus.OK)
    
@api.post(FS_API + "{instance_id}/pull")
async def pull_obj(instance_id: int, data: schemas.Path, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    user, _, drive_manager = response
    end_path = data.cwd + data.path 
    
    file_data = run_async(drive_manager.pull_object(user.discord_id, end_path))
    if isinstance(file_data, errors.T_Error):
        return rich_error_response(file_data)
    
    return JSONResponse(file_data.as_json_response(), status_code=HTTPStatus.OK)
    
@api.post(FS_API + "{instance_id}/read")
async def read_file(instance_id: int, data: schemas.Path, request: Request) -> PlainTextResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, _, drive_manager = response
    end_path = data.cwd + data.path 
    
    struct_base: fs.FS_Dir = run_async(drive_manager.get_struct())
    target = struct_base.move_to(end_path)
    
    if target is None:
        return rich_error_response(errors.INVALID_PATH)
    
    if isinstance(target, fs.FS_Dir):
        return rich_error_response(errors.PATH_TO_DIR)
    
    status = run_async(drive_manager._read_file(target))
    if isinstance(status, errors.T_Error):
        return rich_error_response(status)
    
    return PlainTextResponse(content=status.decode(), status_code=HTTPStatus.OK)
    
@api.post(FS_API + "{instance_id}/write")
async def write_file(instance_id: int, data: schemas.Write, request: Request) -> Response:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, _, drive_manager = response
    end_path = data.cwd + data.path 
    
    struct_base: fs.FS_Dir = run_async(drive_manager.get_struct())
    target = struct_base.move_to(end_path)
    
    if target is None:
        return rich_error_response(errors.INVALID_PATH)
    
    if isinstance(target, fs.FS_Dir):
        return rich_error_response(errors.PATH_TO_DIR)
    
    write_status = run_async(drive_manager.write_file(data.uid, target.path_to(), data.content))
    if isinstance(write_status, errors.T_Error):
        return rich_error_response(write_status)
    
    return Response(status_code=HTTPStatus.OK)
    
@api.post(FS_API + "{instance_id}/upload")
async def upload_file(instance_id: int, data: schemas.Write, request: Request) -> Response:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, _, drive_manager = response
    end_path = data.path 
    
    struct_base: fs.FS_Dir = run_async(drive_manager.get_struct())
    target_parent = struct_base.move_to(data.cwd)

    if target_parent.has_object(data.path):
        return rich_error_response(errors.NAME_IN_USE)
    
    create_status = run_async(drive_manager.create_file(data.uid, end_path))
    if isinstance(create_status, errors.T_Error):
        return rich_error_response(create_status)
    
    write_status = run_async(drive_manager.write_file(data.uid, end_path, data.content, True))
    if isinstance(write_status, errors.T_Error):
        return rich_error_response(write_status)
    
    return Response(status_code=HTTPStatus.OK)


DEBUG_API = "/api/dbg/"

@api.post(DEBUG_API + "{instance_id}/memusage")
async def memory_usage(instance_id: int, data: schemas.Auth, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, _, drive_manager = response
    
    usage = drive_manager.memory_manager.get_memory_usage()
    total_used = sum(usage.values())
    usage_per_bucket = {}

    for i, mem in usage.items():
        percentage = 100.0
        if total_used > 0:
            percentage = round(((mem / total_used) * 100), 2)
        usage_per_bucket[f"data_{i}"] = f"{sizeof_fmt(mem)} ({percentage}%)"
    
    content = {"total": sizeof_fmt(total_used), "per_bucket": usage_per_bucket}
    
    return JSONResponse(content, status_code=HTTPStatus.OK)

@api.post(DEBUG_API + "{instance_id}/dumpcache")
async def dump_cache(instance_id: int, data: schemas.DebugIndex, request: Request) -> PlainTextResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, _, drive_manager = response
    index = data.index
    
    bucket = drive_manager.memory_manager.buckets.get(index)
    if bucket is None:
        return rich_error_response(f"Bucket of index {index} not found.")

    cache_msg = json.dumps(bucket.cache, indent=2)
    
    return PlainTextResponse(cache_msg, status_code=HTTPStatus.OK)

@api.post(DEBUG_API + "{instance_id}/recache")
async def recache(instance_id: int, data: schemas.DebugIndex, request: Request) -> PlainTextResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, guild, drive_manager = response
    index = data.index
    
    bucket = drive_manager.memory_manager.buckets.get(index)
    if bucket is None:
        return rich_error_response(f"Bucket of index {index} not found.")

    new_cache = run_async(bucket._build_cache(guild, index, bucket.data_channels))
    bucket.cache = new_cache
    run_async(bucket._save_cache())

    cache_msg = json.dumps(bucket.cache, indent=2)
    
    return PlainTextResponse(cache_msg, status_code=HTTPStatus.OK)

@api.post(DEBUG_API + "{instance_id}/trace")
async def trace_file(instance_id: int, data: schemas.DebugPath, request: Request) -> JSONResponse:
    status, response = await prepare_restricted_endpoint_data(instance_id, data, request)
    if not status:
        return response
    
    _, _, drive_manager = response
    
    struct: fs.FS_Dir = run_async(drive_manager.get_struct())
    file = struct.move_to(data.path)
    
    raw_trace: list[Message] = run_async(drive_manager.memory_manager.get_content_trace(file.mem_addr))
    trace = [(msg.id, msg.jump_url) for msg in raw_trace]

    return JSONResponse(trace, status_code=HTTPStatus.OK)

