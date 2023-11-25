import os
import time
from typing import ParamSpec, Awaitable

import psycopg

from aleo_types import *
from db import Database
from disasm.aleo import disasm_instruction, disasm_command
from util.global_cache import MappingCacheDict, get_program
from .environment import Registers
from .instruction import execute_instruction
from .utils import load_plaintext_from_operand, store_plaintext_to_register, FinalizeState, load_future_from_register

try:
    from line_profiler import profile
except ImportError:
    P = ParamSpec('P')
    R = TypeVar('R')
    def profile(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            return await func(*args, **kwargs)
        return wrapper


async def mapping_cache_read(db: Database, program_name: str, mapping_name: str) -> MappingCacheDict:
    return await db.get_mapping_cache(program_name, mapping_name)

async def mapping_cache_read_with_cur(db: Database, cur: psycopg.AsyncCursor[dict[str, Any]], program_name: str,
                                      mapping_name: str) -> MappingCacheDict:
    return await db.get_mapping_cache_with_cur(cur, program_name, mapping_name)

class ExecuteError(Exception):
    def __init__(self, message: str, exception: Optional[Exception], instruction: str, program: str = None, function_name: str = None):
        super().__init__(message)
        self.original_exception = exception
        self.instruction = instruction
        self.program = program
        self.function_name = function_name


@profile
async def execute_finalizer(db: Database, cur: Optional[psycopg.AsyncCursor[dict[str, Any]]], finalize_state: FinalizeState,
                            transition_id: TransitionID, program: Program,
                            function_name: Identifier, inputs: list[Value],
                            mapping_cache: Optional[dict[Field, MappingCacheDict]],
                            allow_state_change: bool,
                            execute_await: bool = False) -> list[dict[str, Any]]:
    registers = Registers()
    operations: list[dict[str, Any]] = []
    function = program.functions[function_name]
    if function.finalize.value is None:
        raise ValueError("invalid finalize function")
    finalize = function.finalize.value

    if len(inputs) != len(finalize.inputs):
        raise TypeError("invalid number of inputs")
    for fi, i in zip(finalize.inputs, inputs):
        if fi.finalize_type.type.name != i.type.name:
            raise TypeError("invalid input type")
        ir = fi.register
        if not isinstance(ir, LocatorRegister):
            raise TypeError("invalid input register type")
        registers[int(ir.locator)] = i

    debug = os.environ.get("DEBUG", False)
    timer = time.perf_counter_ns()

    if debug:
        print(f"finalize {program.id}/{function_name}({', '.join(str(i) for i in registers)})")

    pc = 0


    while pc < len(finalize.commands):
        c = finalize.commands[pc]
        if debug:
            if isinstance(c, InstructionCommand):
                print(disasm_instruction(c.instruction))
            else:
                print(disasm_command(c))

        try:
            if isinstance(c, InstructionCommand):
                instruction = c.instruction
                try:
                    execute_instruction(instruction, program, registers, finalize_state)
                except (AssertionError, OverflowError, ZeroDivisionError) as e:
                    raise ExecuteError(str(e), e, disasm_instruction(instruction), str(program.id), str(function_name))
                except Exception:
                    registers.dump()
                    raise

            elif isinstance(c, ContainsCommand):
                mapping_id = Field.loads(cached_get_mapping_id(str(program.id), str(c.mapping)))
                if mapping_cache is not None and mapping_id not in mapping_cache:
                    if cur:
                        mapping_cache[mapping_id] = await mapping_cache_read_with_cur(db, cur, str(program.id), str(c.mapping))
                    else:
                        mapping_cache[mapping_id] = await mapping_cache_read(db, str(program.id), str(c.mapping))
                key = load_plaintext_from_operand(c.key, registers, finalize_state)
                key_id = Field.loads(cached_get_key_id(str(program.id), str(c.mapping), key.dump()))
                if mapping_cache:
                    contains = key_id in mapping_cache[mapping_id]
                else:
                    value = await db.get_mapping_value(str(program.id), str(c.mapping), str(key_id))
                    contains = value is not None
                value = PlaintextValue(
                    plaintext=LiteralPlaintext(
                        literal=Literal(
                            type_=Literal.Type.Boolean,
                            primitive=bool_(contains)
                        )
                    )
                )
                destination = c.destination
                store_plaintext_to_register(value.plaintext, destination, registers)

            elif isinstance(c, GetCommand | GetOrUseCommand):
                mapping_id = Field.loads(cached_get_mapping_id(str(program.id), str(c.mapping)))
                if mapping_cache is not None and mapping_id not in mapping_cache:
                    if cur:
                        mapping_cache[mapping_id] = await mapping_cache_read_with_cur(db, cur, str(program.id), str(c.mapping))
                    else:
                        mapping_cache[mapping_id] = await mapping_cache_read(db, str(program.id), str(c.mapping))
                key = load_plaintext_from_operand(c.key, registers, finalize_state)
                key_id = Field.loads(cached_get_key_id(str(program.id), str(c.mapping), key.dump()))
                if mapping_cache:
                    if key_id not in mapping_cache[mapping_id]:
                        if isinstance(c, GetCommand):
                            raise ExecuteError(f"key {key} not found in mapping {c.mapping}", None, disasm_command(c), str(program.id), str(function_name))
                        default = load_plaintext_from_operand(c.default, registers, finalize_state)
                        value = PlaintextValue(plaintext=default)
                    else:
                        value = mapping_cache[mapping_id][key_id]["value"]
                        if debug:
                            print(f"get {c.mapping}[{key}] = {value}")
                        if not isinstance(value, PlaintextValue):
                            raise TypeError("invalid value type")
                else:
                    value = await db.get_mapping_value(str(program.id), str(c.mapping), str(key_id))
                    if value is None:
                        if isinstance(c, GetCommand):
                            raise ExecuteError(f"key {key} not found in mapping {c.mapping}", None, disasm_command(c), str(program.id), str(function_name))
                        default = load_plaintext_from_operand(c.default, registers, finalize_state)
                        value = PlaintextValue(plaintext=default)
                    else:
                        value = Value.load(BytesIO(value))
                        if not isinstance(value, PlaintextValue):
                            raise TypeError("invalid value type")
                destination = c.destination
                store_plaintext_to_register(value.plaintext, destination, registers)

            elif isinstance(c, SetCommand):
                mapping_id = Field.loads(cached_get_mapping_id(str(program.id), str(c.mapping)))
                if mapping_cache is not None and mapping_id not in mapping_cache:
                    if cur:
                        mapping_cache[mapping_id] = await mapping_cache_read_with_cur(db, cur, str(program.id), str(c.mapping))
                    else:
                        mapping_cache[mapping_id] = await mapping_cache_read(db, str(program.id), str(c.mapping))
                key = load_plaintext_from_operand(c.key, registers, finalize_state)
                value = PlaintextValue(plaintext=load_plaintext_from_operand(c.value, registers, finalize_state))
                key_id = Field.loads(cached_get_key_id(str(program.id), str(c.mapping), key.dump()))
                value_id = Field.loads(aleo_explorer_rust.get_value_id(str(key_id), value.dump()))
                if mapping_cache:
                    if key_id not in mapping_cache[mapping_id]:
                        mapping_cache[mapping_id][key_id] = {
                            "value_id": value_id,
                            "key": key,
                            "value": value,
                        }
                    else:
                        mapping_cache[mapping_id][key_id]["value_id"] = value_id
                        mapping_cache[mapping_id][key_id]["value"] = value
                    if debug:
                        print(f"set {c.mapping}[{key}] = {value}")
                else:
                    if allow_state_change:
                        raise RuntimeError("unsupported execution configuration")
                    else:
                        print("Not updating database because allow_state_change is False")

                operations.append({
                    "type": FinalizeOperation.Type.UpdateKeyValue,
                    "program_name": str(program.id),
                    "mapping_id": mapping_id,
                    "key_id": key_id,
                    "value_id": value_id,
                    "mapping_name": c.mapping,
                    "key": key,
                    "value": value,
                    "height": finalize_state.block_height,
                    "from_transaction": True,
                })

            elif isinstance(c, RandChaChaCommand):
                additional_seeds = list(map(lambda x: PlaintextValue(plaintext=load_plaintext_from_operand(x, registers, finalize_state)).dump(), c.operands))
                chacha_seed = aleo_explorer_rust.chacha_random_seed(
                    finalize_state.random_seed,
                    transition_id.dump(),
                    program.id.dump(),
                    function_name.dump(),
                    int(c.destination.locator),
                    c.destination_type.value,
                    additional_seeds,
                )
                primitive_type = c.destination_type.primitive_type
                value = primitive_type.load(BytesIO(aleo_explorer_rust.chacha_random_value(chacha_seed, c.destination_type)))
                res = LiteralPlaintext(
                    literal=Literal(
                        type_=Literal.Type(c.destination_type.value),
                        primitive=value,
                    )
                )
                store_plaintext_to_register(res, c.destination, registers)

            elif isinstance(c, RemoveCommand):
                mapping_id = Field.loads(cached_get_mapping_id(str(program.id), str(c.mapping)))
                if mapping_cache is not None and mapping_id not in mapping_cache:
                    if cur:
                        mapping_cache[mapping_id] = await mapping_cache_read_with_cur(db, cur, str(program.id), str(c.mapping))
                    else:
                        mapping_cache[mapping_id] = await mapping_cache_read(db, str(program.id), str(c.mapping))
                key = load_plaintext_from_operand(c.key, registers, finalize_state)
                key_id = Field.loads(cached_get_key_id(str(program.id), str(c.mapping), key.dump()))
                if mapping_cache:
                    if key_id not in mapping_cache[mapping_id]:
                        print(f"Key {key} not found in mapping {c.mapping}")
                        pc += 1
                        continue
                    mapping_cache[mapping_id].pop(key_id)
                    if debug:
                        print(f"del {c.mapping}[{key}]")
                else:
                    if allow_state_change:
                        raise RuntimeError("unsupported execution configuration")
                    else:
                        print("Not updating database because allow_state_change is False")
                operations.append({
                    "type": FinalizeOperation.Type.RemoveKeyValue,
                    "program_name": str(program.id),
                    "mapping_id": mapping_id,
                    "mapping_name": c.mapping,
                    "key_id": key_id,
                    "key": key,
                    "height": finalize_state.block_height,
                    "from_transaction": True,
                })

            elif isinstance(c, (BranchEqCommand, BranchNeqCommand)):
                first = load_plaintext_from_operand(c.first, registers, finalize_state)
                second = load_plaintext_from_operand(c.second, registers, finalize_state)
                if (first == second and isinstance(c, BranchEqCommand)) or (first != second and isinstance(c, BranchNeqCommand)):
                    pc = finalize.positions[c.position]
                    continue

            elif isinstance(c, PositionCommand):
                pass

            elif isinstance(c, AwaitCommand):
                if execute_await:
                    call_future = load_future_from_register(c.register, registers, finalize_state)
                    call_program = await get_program(db, str(call_future.program_id))
                    if not call_program:
                        raise RuntimeError("program not found")

                    from interpreter.interpreter import _load_input_from_arguments
                    call_inputs: list[Value] = _load_input_from_arguments(call_future.arguments)
                    operations.extend(
                        await execute_finalizer(db, cur, finalize_state, transition_id, call_program, call_future.function_name, call_inputs, mapping_cache, allow_state_change)
                    )

            else:
                raise NotImplementedError

        except IndexError as e:
            raise ExecuteError(f"r{e} does not exist", e, disasm_command(c), str(program.id), str(function_name))

        pc += 1

        if debug:
            registers.dump()
    if debug:
        print(f"execution took {time.perf_counter_ns() - timer} ns")
    return operations




