from io import BytesIO

import aleo_explorer_rust
from starlette.requests import Request
from starlette.responses import JSONResponse

from aleo_types import Program, Value, LiteralPlaintextType, LiteralPlaintext, \
    Literal, StructPlaintextType, StructPlaintext
from api.utils import async_check_sync, use_program_cache
from db import Database


@async_check_sync
@use_program_cache
async def mapping_route(request: Request, program_cache: dict[str, Program]):
    db: Database = request.app.state.db
    _ = request.path_params["version"]
    program_id = request.path_params["program_id"]
    mapping = request.path_params["mapping"]
    key = request.path_params["key"]
    try:
        program = program_cache[program_id]
    except KeyError:
        program = await db.get_program(program_id)
        if not program:
            return JSONResponse({"error": "Program not found"}, status_code=404)
        program = Program.load(BytesIO(program))
        program_cache[program_id] = program
    if mapping not in program.mappings:
        return JSONResponse({"error": "Mapping not found"}, status_code=404)
    map_key_type = program.mappings[mapping].key.plaintext_type
    if isinstance(map_key_type, LiteralPlaintextType):
        primitive_type = map_key_type.literal_type.primitive_type
        try:
            key = primitive_type.loads(key)
        except:
            return JSONResponse({"error": "Invalid key"}, status_code=400)
        key = LiteralPlaintext(literal=Literal(type_=Literal.reverse_primitive_type_map[primitive_type], primitive=key))
    elif isinstance(map_key_type, StructPlaintextType):
        structs = program.structs
        struct_type = structs[map_key_type.struct]
        try:
            value = StructPlaintext.loads(key, struct_type, structs)
        except Exception as e:
            return JSONResponse({"error": f"Invalid struct key: {e} (experimental feature, if you believe this is an error please submit a feedback)"}, status_code=400)
        key = value
    else:
        return JSONResponse({"error": "Unknown key type"}, status_code=500)
    key_id = aleo_explorer_rust.get_key_id(program_id, mapping, key.dump())
    value = await db.get_mapping_value(program_id, mapping, key_id)
    if value is None:
        return JSONResponse(None)
    return JSONResponse(str(Value.load(BytesIO(value))))

@async_check_sync
@use_program_cache
async def mapping_list_route(request: Request, program_cache: dict[str, Program]):
    db: Database = request.app.state.db
    _ = request.path_params["version"]
    program_id = request.path_params["program_id"]
    try:
        program = program_cache[program_id]
    except KeyError:
        program = await db.get_program(program_id)
        if not program:
            return JSONResponse({"error": "Program not found"}, status_code=404)
        program = Program.load(BytesIO(program))
        program_cache[program_id] = program
    mappings = program.mappings
    return JSONResponse(list(map(str, mappings.keys())))

@async_check_sync
@use_program_cache
async def mapping_value_list_route(request: Request, program_cache: dict[str, Program]):
    db: Database = request.app.state.db
    _ = request.path_params["version"]
    program_id = request.path_params["program_id"]
    mapping = request.path_params["mapping"]
    try:
        program = program_cache[program_id]
    except KeyError:
        program = await db.get_program(program_id)
        if not program:
            return JSONResponse({"error": "Program not found"}, status_code=404)
        program = Program.load(BytesIO(program))
        program_cache[program_id] = program
    mappings = program.mappings
    if mapping not in mappings:
        return JSONResponse({"error": "Mapping not found"}, status_code=404)
    mapping_cache = await db.get_mapping_cache(program_id, mapping)
    res: dict[str, dict[str, str]] = {}
    for key_id, item in mapping_cache.items():
        res[str(key_id)] = {
            "key": str(item["key"]),
            "value": str(item["value"]),
            "value_id": str(item["value_id"]),
        }
    return JSONResponse(res)