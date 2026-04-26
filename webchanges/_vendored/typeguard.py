"""
Vendored version of typeguard._functions.check_type() from typeguard v4.51 released on 19-Feb-26
https://github.com/agronholm/typeguard/releases/tag/4.5.1.
(code https://github.com/agronholm/typeguard/tree/67cae3dc3b3984a1a0e87389937fe118ed6b4328).

Allows us to load this function in case typeguard is not installed.
"""

# This is the MIT license: http://www.opensource.org/licenses/mit-license.php
#
# Copyright (c) Alex Grönholm
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this
# software and associated documentation files (the "Software"), to deal in the Software
# without restriction, including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
# to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
# FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from __future__ import annotations
from dataclasses import dataclass
from collections import deque

import collections.abc
import inspect
import sys
import types
import typing
import warnings
from collections.abc import Mapping, MutableMapping, Sequence
from enum import Enum, auto
from inspect import Parameter, isclass, isfunction, currentframe
from io import BufferedIOBase, IOBase, RawIOBase, TextIOBase
from itertools import zip_longest
from textwrap import indent
from typing import (
    IO,
    AbstractSet,
    Annotated,
    Any,
    BinaryIO,
    Callable,
    Dict,
    ForwardRef,
    List,
    NewType,
    Optional,
    Set,
    TextIO,
    Tuple,
    Type,
    TypeVar,
    Union, Deque, Iterable, cast, overload, ParamSpec,
)
from unittest.mock import Mock

import typing_extensions

# Must use this because typing.is_typeddict does not recognize
# TypedDict from typing_extensions, and as of version 4.12.0
# typing_extensions.TypedDict is different from typing.TypedDict
# on all versions.
from typing_extensions import is_typeddict

T = TypeVar("T")

# Sentinel for missing TypedDict keys
_missing = object()

# from . import _suppression
class _suppression():
    """Representation of https://github.com/agronholm/typeguard/blob/67cae3dc3b3984a1a0e87389937fe118ed6b4328/src/typeguard/_suppression.py#L18"""
    type_checks_suppressed = 0


# from ._config import CollectionCheckStrategy, ForwardRefPolicy

class CollectionCheckStrategy(Enum):
    """
    Specifies how thoroughly the contents of collections are type checked.

    This has an effect on the following built-in checkers:

    * ``AbstractSet``
    * ``Dict``
    * ``List``
    * ``Mapping``
    * ``Set``
    * ``Tuple[<type>, ...]`` (arbitrarily sized tuples)

    Members:

    * ``FIRST_ITEM``: check only the first item
    * ``ALL_ITEMS``: check all items
    """

    FIRST_ITEM = auto()
    ALL_ITEMS = auto()

    def iterate_samples(self, collection: Iterable[T]) -> Iterable[T]:
        if self is CollectionCheckStrategy.FIRST_ITEM:
            try:
                return [next(iter(collection))]
            except StopIteration:
                return ()
        else:
            return collection

class ForwardRefPolicy(Enum):
    """
    Defines how unresolved forward references are handled.

    Members:

    * ``ERROR``: propagate the :exc:`NameError` when the forward reference lookup fails
    * ``WARN``: emit a :class:`~.TypeHintWarning` if the forward reference lookup fails
    * ``IGNORE``: silently skip checks for unresolveable forward references
    """

    ERROR = auto()
    WARN = auto()
    IGNORE = auto()


# from ._exceptions import TypeCheckError, TypeHintWarning

class TypeHintWarning(UserWarning):
    """
    A warning that is emitted when a type hint in string form could not be resolved to
    an actual type.
    """


class TypeCheckError(Exception):
    """
    Raised by typeguard's type checkers when a type mismatch is detected.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self._path: Deque[str] = deque()

    def append_path_element(self, element: str) -> None:
        self._path.append(element)

    def __str__(self) -> str:
        if self._path:
            return " of ".join(self._path) + " " + str(self.args[0])
        else:
            return str(self.args[0])

# from ._memo import TypeCheckMemo

# > from typeguard._config import TypeCheckConfiguration, global_config

TypeCheckFailCallback: TypeAlias = Callable[[TypeCheckError, 'TypeCheckMemo'], Any]

@dataclass
class TypeCheckConfiguration:
    """
     You can change Typeguard's behavior with these settings.

    .. attribute:: typecheck_fail_callback
       :type: Callable[[TypeCheckError, TypeCheckMemo], Any]

         Callable that is called when type checking fails.

         Default: ``None`` (the :exc:`~.TypeCheckError` is raised directly)

    .. attribute:: forward_ref_policy
       :type: ForwardRefPolicy

         Specifies what to do when a forward reference fails to resolve.

         Default: ``WARN``

    .. attribute:: collection_check_strategy
       :type: CollectionCheckStrategy

         Specifies how thoroughly the contents of collections (list, dict, etc.) are
         type checked.

         Default: ``FIRST_ITEM``

    .. attribute:: debug_instrumentation
       :type: bool

         If set to ``True``, the code of modules or functions instrumented by typeguard
         is printed to ``sys.stderr`` after the instrumentation is done

         Default: ``False``
    """

    forward_ref_policy: ForwardRefPolicy = ForwardRefPolicy.WARN
    typecheck_fail_callback: TypeCheckFailCallback | None = None
    collection_check_strategy: CollectionCheckStrategy = (
        CollectionCheckStrategy.FIRST_ITEM
    )
    debug_instrumentation: bool = False


global_config = TypeCheckConfiguration()

class TypeCheckMemo:
    """
    Contains information necessary for type checkers to do their work.

    .. attribute:: globals
       :type: dict[str, Any]

        Dictionary of global variables to use for resolving forward references.

    .. attribute:: locals
       :type: dict[str, Any]

        Dictionary of local variables to use for resolving forward references.

    .. attribute:: self_type
       :type: type | None

        When running type checks within an instance method or class method, this is the
        class object that the first argument (usually named ``self`` or ``cls``) refers
        to.

    .. attribute:: config
       :type: TypeCheckConfiguration

         Contains the configuration for a particular set of type checking operations.
    """

    __slots__ = "globals", "locals", "self_type", "config"

    def __init__(
        self,
        globals: dict[str, Any],
        locals: dict[str, Any],
        *,
        self_type: type | None = None,
        config: TypeCheckConfiguration = global_config,
    ):
        self.globals = globals
        self.locals = locals
        self.self_type = self_type
        self.config = config

# from ._utils import evaluate_forwardref, get_stacklevel, get_type_name, qualified_name

if sys.version_info >= (3, 14):

    def evaluate_forwardref(forwardref: ForwardRef, memo: TypeCheckMemo) -> Any:
        # If the ForwardRef has a module, try that module's namespace first.
        # This is needed because Python 3.14's ForwardRef.evaluate() requires
        # all referenced names to be available in the provided globals/locals.
        if getattr(forwardref, "__forward_module__", None):
            try:
                # Not passing globals / locals defaults to those of the caller
                return forwardref.evaluate(type_params=())
            except NameError:
                # Fall back to caller's namespace for backwards compatibility
                pass

        return forwardref.evaluate(
            globals=memo.globals, locals=memo.locals, type_params=()
        )
elif sys.version_info >= (3, 13):

    def evaluate_forwardref(forwardref: ForwardRef, memo: TypeCheckMemo) -> Any:
        return forwardref._evaluate(
            memo.globals, memo.locals, type_params=(), recursive_guard=frozenset()
        )
else:

    def evaluate_forwardref(forwardref: ForwardRef, memo: TypeCheckMemo) -> Any:
        try:
            return forwardref._evaluate(
                memo.globals, memo.locals, recursive_guard=frozenset()
            )
        except NameError:
            if sys.version_info < (3, 10):
                # Try again, with the type substitutions (list -> List etc.) in place
                new_globals = memo.globals.copy()
                new_globals.setdefault("Union", Union)

                return forwardref._evaluate(
                    new_globals, memo.locals or new_globals, recursive_guard=frozenset()
                )

            raise

def get_type_name(type_: Any) -> str:
    name: str
    for attrname in "__name__", "_name", "__forward_arg__":
        candidate = getattr(type_, attrname, None)
        if isinstance(candidate, str):
            name = candidate
            break
    else:
        origin = get_origin(type_)
        candidate = getattr(origin, "_name", None)
        if candidate is None:
            candidate = type_.__class__.__name__.strip("_")

        if isinstance(candidate, str):
            name = candidate
        else:
            return "(unknown)"

    args = get_args(type_)
    if args:
        if name == "Literal":
            formatted_args = ", ".join(repr(arg) for arg in args)
        else:
            formatted_args = ", ".join(get_type_name(arg) for arg in args)

        name += f"[{formatted_args}]"

    # For ForwardRefs, use the module stored on the object if available
    if hasattr(type_, "__forward_module__"):
        module = type_.__forward_module__
    else:
        module = getattr(type_, "__module__", None)
    if module and module not in (None, "typing", "typing_extensions", "builtins"):
        name = module + "." + name

    return name


def qualified_name(obj: Any, *, add_class_prefix: bool = False) -> str:
    """
    Return the qualified name (e.g. package.module.Type) for the given object.

    Builtins and types from the :mod:`typing` package get special treatment by having
    the module name stripped from the generated name.

    """
    if obj is None:
        return "None"
    elif inspect.isclass(obj):
        prefix = "class " if add_class_prefix else ""
        type_ = obj
    else:
        prefix = ""
        type_ = type(obj)

    module = type_.__module__
    qualname = type_.__qualname__
    name = qualname if module in ("typing", "builtins") else f"{module}.{qualname}"
    return prefix + name

def get_stacklevel() -> int:
    level = 1
    frame = cast(types.FrameType, currentframe()).f_back
    while frame and frame.f_globals.get("__name__", "").startswith("typeguard."):
        level += 1
        frame = frame.f_back

    return level


# -------------------------

if sys.version_info >= (3, 15):
    from typing import NoExtraItems
else:
    from typing_extensions import NoExtraItems

if sys.version_info >= (3, 11):
    from typing import (
        NotRequired,
        Required,
        TypeAlias,
        get_args,
        get_origin,
    )

    SubclassableAny = Any
else:
    from typing_extensions import Any as SubclassableAny
    from typing_extensions import (
        NotRequired,
        Required,
        TypeAlias,
        get_args,
        get_origin,
    )

TypeCheckerCallable: TypeAlias = Callable[
    [Any, Any, Tuple[Any, ...], TypeCheckMemo], Any
]
TypeCheckLookupCallback: TypeAlias = Callable[
    [Any, Tuple[Any, ...], Tuple[Any, ...]], Optional[TypeCheckerCallable]
]

generic_alias_types: tuple[type, ...] = (
    type(List),
    type(List[Any]),
    types.GenericAlias,
)


def check_callable(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if not callable(value):
        raise TypeCheckError("is not callable")

    if args:
        try:
            signature = inspect.signature(value)
        except (TypeError, ValueError):
            return

        argument_types = args[0]
        if isinstance(argument_types, list) and not any(
            type(item) is ParamSpec for item in argument_types
        ):
            # The callable must not have keyword-only arguments without defaults
            unfulfilled_kwonlyargs = [
                param.name
                for param in signature.parameters.values()
                if param.kind == Parameter.KEYWORD_ONLY
                and param.default == Parameter.empty
            ]
            if unfulfilled_kwonlyargs:
                raise TypeCheckError(
                    f"has mandatory keyword-only arguments in its declaration: "
                    f"{', '.join(unfulfilled_kwonlyargs)}"
                )

            num_positional_args = num_mandatory_pos_args = 0
            has_varargs = False
            for param in signature.parameters.values():
                if param.kind in (
                    Parameter.POSITIONAL_ONLY,
                    Parameter.POSITIONAL_OR_KEYWORD,
                ):
                    num_positional_args += 1
                    if param.default is Parameter.empty:
                        num_mandatory_pos_args += 1
                elif param.kind == Parameter.VAR_POSITIONAL:
                    has_varargs = True

            if num_mandatory_pos_args > len(argument_types):
                raise TypeCheckError(
                    f"has too many mandatory positional arguments in its declaration; "
                    f"expected {len(argument_types)} but {num_mandatory_pos_args} "
                    f"mandatory positional argument(s) declared"
                )
            elif not has_varargs and num_positional_args < len(argument_types):
                raise TypeCheckError(
                    f"has too few arguments in its declaration; expected "
                    f"{len(argument_types)} but {num_positional_args} argument(s) "
                    f"declared"
                )


def check_mapping(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if origin_type is Dict or origin_type is dict:
        if not isinstance(value, dict):
            raise TypeCheckError("is not a dict")
    if origin_type is MutableMapping or origin_type is collections.abc.MutableMapping:
        if not isinstance(value, collections.abc.MutableMapping):
            raise TypeCheckError("is not a mutable mapping")
    elif not isinstance(value, collections.abc.Mapping):
        raise TypeCheckError("is not a mapping")

    if args:
        key_type, value_type = args
        if key_type is not Any or value_type is not Any:
            samples = memo.config.collection_check_strategy.iterate_samples(
                value.items()
            )
            for k, v in samples:
                try:
                    check_type_internal(k, key_type, memo)
                except TypeCheckError as exc:
                    exc.append_path_element(f"key {k!r}")
                    raise

                try:
                    check_type_internal(v, value_type, memo)
                except TypeCheckError as exc:
                    exc.append_path_element(f"value of key {k!r}")
                    raise


def check_typed_dict(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if not isinstance(value, dict):
        raise TypeCheckError("is not a dict")

    declared_keys = frozenset(origin_type.__annotations__)
    required_keys = set(origin_type.__required_keys__)
    existing_keys = set(value)
    if extra_keys := existing_keys - declared_keys:
        if (
            argtype := getattr(origin_type, "__extra_items__", NoExtraItems)
        ) is NoExtraItems:
            keys_formatted = ", ".join(
                f'"{key}"' for key in sorted(extra_keys, key=repr)
            )
            raise TypeCheckError(f"has unexpected extra key(s): {keys_formatted}")

        for key in extra_keys:
            argvalue = value[key]
            try:
                check_type_internal(argvalue, argtype, memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"value of key {key!r}")
                raise

    # Detect NotRequired fields which are hidden by get_type_hints()
    type_hints: dict[str, type] = {}
    for key, annotation in origin_type.__annotations__.items():
        if isinstance(annotation, ForwardRef):
            annotation = evaluate_forwardref(annotation, memo)

        if get_origin(annotation) is NotRequired:
            required_keys.discard(key)
            annotation = get_args(annotation)[0]
        elif get_origin(annotation) is Required:
            required_keys.add(key)
            annotation = get_args(annotation)[0]

        type_hints[key] = annotation

    if missing_keys := required_keys - existing_keys:
        keys_formatted = ", ".join(f'"{key}"' for key in sorted(missing_keys, key=repr))
        raise TypeCheckError(f"is missing required key(s): {keys_formatted}")

    for key, argtype in type_hints.items():
        argvalue = value.get(key, _missing)
        if argvalue is not _missing:
            try:
                check_type_internal(argvalue, argtype, memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"value of key {key!r}")
                raise


def check_list(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if not isinstance(value, list):
        raise TypeCheckError("is not a list")

    if args and args != (Any,):
        samples = memo.config.collection_check_strategy.iterate_samples(value)
        for i, v in enumerate(samples):
            try:
                check_type_internal(v, args[0], memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"item {i}")
                raise


def check_sequence(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if not isinstance(value, collections.abc.Sequence):
        raise TypeCheckError("is not a sequence")

    if args and args != (Any,):
        samples = memo.config.collection_check_strategy.iterate_samples(value)
        for i, v in enumerate(samples):
            try:
                check_type_internal(v, args[0], memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"item {i}")
                raise


def check_set(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if origin_type is frozenset:
        if not isinstance(value, frozenset):
            raise TypeCheckError("is not a frozenset")
    elif not isinstance(value, AbstractSet):
        raise TypeCheckError("is not a set")

    if args and args != (Any,):
        samples = memo.config.collection_check_strategy.iterate_samples(value)
        for v in samples:
            try:
                check_type_internal(v, args[0], memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"[{v}]")
                raise


def check_tuple(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    # Specialized check for NamedTuples
    if field_types := getattr(origin_type, "__annotations__", None):
        if not isinstance(value, origin_type):
            raise TypeCheckError(
                f"is not a named tuple of type {qualified_name(origin_type)}"
            )

        for name, field_type in field_types.items():
            try:
                check_type_internal(getattr(value, name), field_type, memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"attribute {name!r}")
                raise

        return
    elif not isinstance(value, tuple):
        raise TypeCheckError("is not a tuple")

    if args:
        use_ellipsis = args[-1] is Ellipsis
        tuple_params = args[: -1 if use_ellipsis else None]
    else:
        # Unparametrized Tuple or plain tuple
        return

    if use_ellipsis:
        element_type = tuple_params[0]
        samples = memo.config.collection_check_strategy.iterate_samples(value)
        for i, element in enumerate(samples):
            try:
                check_type_internal(element, element_type, memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"item {i}")
                raise
    elif tuple_params == ((),):
        if value != ():
            raise TypeCheckError("is not an empty tuple")
    else:
        if len(value) != len(tuple_params):
            raise TypeCheckError(
                f"has wrong number of elements (expected {len(tuple_params)}, got "
                f"{len(value)} instead)"
            )

        for i, (element, element_type) in enumerate(zip(value, tuple_params)):
            try:
                check_type_internal(element, element_type, memo)
            except TypeCheckError as exc:
                exc.append_path_element(f"item {i}")
                raise


def check_union(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    errors: dict[str, TypeCheckError] = {}
    try:
        for type_ in args:
            try:
                check_type_internal(value, type_, memo)
                return
            except TypeCheckError as exc:
                errors[get_type_name(type_)] = exc

        formatted_errors = indent(
            "\n".join(f"{key}: {error}" for key, error in errors.items()), "  "
        )
    finally:
        del errors  # avoid creating ref cycle

    raise TypeCheckError(f"did not match any element in the union:\n{formatted_errors}")


def check_uniontype(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if not args:
        return check_instance(value, types.UnionType, (), memo)

    errors: dict[str, TypeCheckError] = {}
    try:
        for type_ in args:
            try:
                check_type_internal(value, type_, memo)
                return
            except TypeCheckError as exc:
                errors[get_type_name(type_)] = exc

        formatted_errors = indent(
            "\n".join(f"{key}: {error}" for key, error in errors.items()), "  "
        )
    finally:
        del errors  # avoid creating ref cycle

    raise TypeCheckError(f"did not match any element in the union:\n{formatted_errors}")


def check_class(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if not isclass(value) and not isinstance(value, generic_alias_types):
        raise TypeCheckError("is not a class")

    if not args:
        return

    if isinstance(args[0], ForwardRef):
        expected_class = evaluate_forwardref(args[0], memo)
    else:
        expected_class = args[0]

    if type(expected_class) in type_alias_types:
        expected_class = expected_class.__value__

    if expected_class is Any:
        return
    elif expected_class is typing_extensions.Self:
        check_self(value, get_origin(expected_class), get_args(expected_class), memo)
    elif getattr(expected_class, "_is_protocol", False):
        check_protocol(value, expected_class, (), memo)
    elif isinstance(expected_class, TypeVar):
        check_typevar(value, expected_class, (), memo, subclass_check=True)
    elif get_origin(expected_class) is Union:
        errors: dict[str, TypeCheckError] = {}
        try:
            for arg in get_args(expected_class):
                if arg is Any:
                    return

                try:
                    check_class(value, type, (arg,), memo)
                    return
                except TypeCheckError as exc:
                    errors[get_type_name(arg)] = exc
            else:
                formatted_errors = indent(
                    "\n".join(f"{key}: {error}" for key, error in errors.items()), "  "
                )
                raise TypeCheckError(
                    f"did not match any element in the union:\n{formatted_errors}"
                )
        finally:
            del errors  # avoid creating ref cycle
    else:
        if isinstance(expected_class, generic_alias_types):
            expected_class = get_origin(expected_class)

        if isinstance(value, generic_alias_types):
            value = get_origin(value)

        if not issubclass(value, expected_class):
            raise TypeCheckError(
                f"is not a subclass of {qualified_name(expected_class)}"
            )


def check_newtype(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    check_type_internal(value, origin_type.__supertype__, memo)


def check_instance(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if not isinstance(value, origin_type):
        raise TypeCheckError(f"is not an instance of {qualified_name(origin_type)}")


def check_typevar(
    value: Any,
    origin_type: TypeVar,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
    *,
    subclass_check: bool = False,
) -> None:
    if origin_type.__bound__ is not None:
        annotation = (
            type[origin_type.__bound__] if subclass_check else origin_type.__bound__
        )
        check_type_internal(value, annotation, memo)
    elif origin_type.__constraints__:
        for constraint in origin_type.__constraints__:
            annotation = Type[constraint] if subclass_check else constraint
            try:
                check_type_internal(value, annotation, memo)
            except TypeCheckError:
                pass
            else:
                break
        else:
            formatted_constraints = ", ".join(
                get_type_name(constraint) for constraint in origin_type.__constraints__
            )
            raise TypeCheckError(
                f"does not match any of the constraints ({formatted_constraints})"
            )


def _is_literal_type(typ: object) -> bool:
    return typ is typing.Literal or typ is typing_extensions.Literal


def check_literal(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    def get_literal_args(literal_args: tuple[Any, ...]) -> tuple[Any, ...]:
        retval: list[Any] = []
        for arg in literal_args:
            if _is_literal_type(get_origin(arg)):
                retval.extend(get_literal_args(arg.__args__))
            elif arg is None or isinstance(arg, (int, str, bytes, bool, Enum)):
                retval.append(arg)
            else:
                raise TypeError(
                    f"Illegal literal value: {arg}"
                )  # TypeError here is deliberate

        return tuple(retval)

    final_args = tuple(get_literal_args(args))
    try:
        index = final_args.index(value)
    except ValueError:
        pass
    else:
        if type(final_args[index]) is type(value):
            return

    formatted_args = ", ".join(repr(arg) for arg in final_args)
    raise TypeCheckError(f"is not any of ({formatted_args})") from None


def check_literal_string(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    check_type_internal(value, str, memo)


def check_typeguard(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    check_type_internal(value, bool, memo)


def check_none(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if value is not None:
        raise TypeCheckError("is not None")


def check_number(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if origin_type is complex and not isinstance(value, (complex, float, int)):
        raise TypeCheckError("is neither complex, float or int")
    elif origin_type is float and not isinstance(value, (float, int)):
        raise TypeCheckError("is neither float or int")


def check_io(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if origin_type is TextIO or (origin_type is IO and args == (str,)):
        if not isinstance(value, TextIOBase):
            raise TypeCheckError("is not a text based I/O object")
    elif origin_type is BinaryIO or (origin_type is IO and args == (bytes,)):
        if not isinstance(value, (RawIOBase, BufferedIOBase)):
            raise TypeCheckError("is not a binary I/O object")
    elif not isinstance(value, IOBase):
        raise TypeCheckError("is not an I/O object")


def check_signature_compatible(subject: type, protocol: type, attrname: str) -> None:
    subject_attr = getattr(subject, attrname)
    try:
        subject_sig = inspect.signature(subject_attr)
    except ValueError:
        return  # this can happen with builtins where the signature cannot be retrieved

    protocol_sig = inspect.signature(getattr(protocol, attrname))
    protocol_type: typing.Literal["instance", "class", "static"] = "instance"
    subject_type: typing.Literal["instance", "class", "static"] = "instance"

    # Check if the protocol-side method is a class method or static method
    for klass in protocol.__mro__:
        if attrname in klass.__dict__:
            descriptor = klass.__dict__[attrname]
            if isinstance(descriptor, staticmethod):
                protocol_type = "static"
            elif isinstance(descriptor, classmethod):
                protocol_type = "class"

            break

    # Check if the subject-side method is a class method or static method
    for klass in subject.__mro__:
        if attrname in klass.__dict__:
            descriptor = klass.__dict__[attrname]
            if isinstance(descriptor, staticmethod):
                subject_type = "static"
            elif isinstance(descriptor, classmethod):
                subject_type = "class"

            break

    if protocol_type == "instance" and subject_type != "instance":
        raise TypeCheckError(
            f"should be an instance method but it's a {subject_type} method"
        )
    elif protocol_type != "instance" and subject_type == "instance":
        raise TypeCheckError(
            f"should be a {protocol_type} method but it's an instance method"
        )

    expected_varargs = any(
        param
        for param in protocol_sig.parameters.values()
        if param.kind is Parameter.VAR_POSITIONAL
    )
    has_varargs = any(
        param
        for param in subject_sig.parameters.values()
        if param.kind is Parameter.VAR_POSITIONAL
    )
    if expected_varargs and not has_varargs:
        raise TypeCheckError("should accept variable positional arguments but doesn't")

    protocol_has_varkwargs = any(
        param
        for param in protocol_sig.parameters.values()
        if param.kind is Parameter.VAR_KEYWORD
    )
    subject_has_varkwargs = any(
        param
        for param in subject_sig.parameters.values()
        if param.kind is Parameter.VAR_KEYWORD
    )
    if protocol_has_varkwargs and not subject_has_varkwargs:
        raise TypeCheckError("should accept variable keyword arguments but doesn't")

    # Check that the callable has at least the expect amount of positional-only
    # arguments (and no extra positional-only arguments without default values)
    if not has_varargs:
        protocol_args = [
            param
            for param in protocol_sig.parameters.values()
            if param.kind
            in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
        ]
        subject_args = [
            param
            for param in subject_sig.parameters.values()
            if param.kind
            in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
        ]

        # Remove the "self" parameter from the protocol arguments to match
        if protocol_type == "instance":
            protocol_args.pop(0)

        # Remove the "self" parameter from the subject arguments to match
        if subject_type == "instance":
            subject_args.pop(0)

        for protocol_arg, subject_arg in zip_longest(protocol_args, subject_args):
            if protocol_arg is None:
                if subject_arg.default is Parameter.empty:
                    raise TypeCheckError("has too many mandatory positional arguments")

                break

            if subject_arg is None:
                raise TypeCheckError("has too few positional arguments")

            if (
                protocol_arg.kind is Parameter.POSITIONAL_OR_KEYWORD
                and subject_arg.kind is Parameter.POSITIONAL_ONLY
            ):
                raise TypeCheckError(
                    f"has an argument ({subject_arg.name}) that should not be "
                    f"positional-only"
                )

            if (
                protocol_arg.kind is Parameter.POSITIONAL_OR_KEYWORD
                and protocol_arg.name != subject_arg.name
            ):
                raise TypeCheckError(
                    f"has a positional argument ({subject_arg.name}) that should be "
                    f"named {protocol_arg.name!r} at this position"
                )

    protocol_kwonlyargs = {
        param.name: param
        for param in protocol_sig.parameters.values()
        if param.kind is Parameter.KEYWORD_ONLY
    }
    subject_kwonlyargs = {
        param.name: param
        for param in subject_sig.parameters.values()
        if param.kind is Parameter.KEYWORD_ONLY
    }
    if not subject_has_varkwargs:
        # Check that the signature has at least the required keyword-only arguments, and
        # no extra mandatory keyword-only arguments
        if missing_kwonlyargs := [
            param.name
            for param in protocol_kwonlyargs.values()
            if param.name not in subject_kwonlyargs
        ]:
            raise TypeCheckError(
                "is missing keyword-only arguments: " + ", ".join(missing_kwonlyargs)
            )

    if not protocol_has_varkwargs:
        if extra_kwonlyargs := [
            param.name
            for param in subject_kwonlyargs.values()
            if param.default is Parameter.empty
            and param.name not in protocol_kwonlyargs
        ]:
            raise TypeCheckError(
                "has mandatory keyword-only arguments not present in the protocol: "
                + ", ".join(extra_kwonlyargs)
            )


def check_protocol(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    origin_annotations = typing.get_type_hints(origin_type)
    for attrname in sorted(typing_extensions.get_protocol_members(origin_type)):
        if (annotation := origin_annotations.get(attrname)) is not None:
            try:
                subject_member = getattr(value, attrname)
            except AttributeError:
                raise TypeCheckError(
                    f"is not compatible with the {origin_type.__qualname__} "
                    f"protocol because it has no attribute named {attrname!r}"
                ) from None

            try:
                check_type_internal(subject_member, annotation, memo)
            except TypeCheckError as exc:
                raise TypeCheckError(
                    f"is not compatible with the {origin_type.__qualname__} "
                    f"protocol because its {attrname!r} attribute {exc}"
                ) from None
        elif callable(getattr(origin_type, attrname)):
            try:
                subject_member = getattr(value, attrname)
            except AttributeError:
                raise TypeCheckError(
                    f"is not compatible with the {origin_type.__qualname__} "
                    f"protocol because it has no method named {attrname!r}"
                ) from None

            if not callable(subject_member):
                raise TypeCheckError(
                    f"is not compatible with the {origin_type.__qualname__} "
                    f"protocol because its {attrname!r} attribute is not a callable"
                )

            # TODO: implement assignability checks for parameter and return value
            #  annotations
            subject = value if isclass(value) else value.__class__
            try:
                check_signature_compatible(subject, origin_type, attrname)
            except TypeCheckError as exc:
                raise TypeCheckError(
                    f"is not compatible with the {origin_type.__qualname__} "
                    f"protocol because its {attrname!r} method {exc}"
                ) from None


def check_byteslike(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if not isinstance(value, (bytearray, bytes, memoryview)):
        raise TypeCheckError("is not bytes-like")


def check_self(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    if memo.self_type is None:
        raise TypeCheckError("cannot be checked against Self outside of a method call")

    if isclass(value):
        if not issubclass(value, memo.self_type):
            raise TypeCheckError(
                f"is not a subclass of the self type ({qualified_name(memo.self_type)})"
            )
    elif not isinstance(value, memo.self_type):
        raise TypeCheckError(
            f"is not an instance of the self type ({qualified_name(memo.self_type)})"
        )


def check_paramspec(
    value: Any,
    origin_type: Any,
    args: tuple[Any, ...],
    memo: TypeCheckMemo,
) -> None:
    pass  # No-op for now (matches upstream)


checker_lookup_functions: list[TypeCheckLookupCallback] = []

def check_type_internal(
    value: Any,
    annotation: Any,
    memo: TypeCheckMemo,
) -> None:
    """
    Check that the given object is compatible with the given type annotation.

    This function should only be used by type checker callables. Applications should use
    :func:`~.check_type` instead.

    :param value: the value to check
    :param annotation: the type annotation to check against
    :param memo: a memo object containing configuration and information necessary for
        looking up forward references
    """

    if isinstance(annotation, ForwardRef):
        try:
            annotation = evaluate_forwardref(annotation, memo)
        except NameError:
            if memo.config.forward_ref_policy is ForwardRefPolicy.ERROR:
                raise
            elif memo.config.forward_ref_policy is ForwardRefPolicy.WARN:
                warnings.warn(
                    f"Cannot resolve forward reference {annotation.__forward_arg__!r}",
                    TypeHintWarning,
                    stacklevel=get_stacklevel(),
                )

            return

    if type(annotation) in type_alias_types:
        annotation = annotation.__value__

    if annotation is Any or annotation is SubclassableAny or isinstance(value, Mock):
        return

    # Skip type checks if value is an instance of a class that inherits from Any
    if not isclass(value) and SubclassableAny in type(value).__bases__:
        return

    extras: tuple[Any, ...]
    origin_type = get_origin(annotation)
    if origin_type is Annotated:
        annotation, *extras_ = get_args(annotation)
        extras = tuple(extras_)
        origin_type = get_origin(annotation)
    else:
        extras = ()

    if origin_type is not None:
        args = get_args(annotation)

        # Compatibility hack to distinguish between unparametrized and empty tuple
        # (tuple[()]), necessary due to https://github.com/python/cpython/issues/91137
        if origin_type in (tuple, Tuple) and annotation is not Tuple and not args:
            args = ((),)
    else:
        origin_type = annotation
        args = ()

    for lookup_func in checker_lookup_functions:
        checker = lookup_func(origin_type, args, extras)
        if checker:
            checker(value, origin_type, args, memo)
            return

    if isclass(origin_type):
        if not isinstance(value, origin_type):
            raise TypeCheckError(f"is not an instance of {qualified_name(origin_type)}")
    elif type(origin_type) is str:  # noqa: E721
        warnings.warn(
            f"Skipping type check against {origin_type!r}; this looks like a "
            f"string-form forward reference imported from another module",
            TypeHintWarning,
            stacklevel=get_stacklevel(),
        )


# Equality checks are applied to these
origin_type_checkers: dict[
    Any, Callable[[Any, Any, tuple[Any, ...], TypeCheckMemo], None]
] = {
    bytes: check_byteslike,
    AbstractSet: check_set,
    BinaryIO: check_io,
    Callable: check_callable,
    collections.abc.Callable: check_callable,
    complex: check_number,
    dict: check_mapping,
    Dict: check_mapping,
    float: check_number,
    frozenset: check_set,
    IO: check_io,
    list: check_list,
    List: check_list,
    typing.Literal: check_literal,
    Mapping: check_mapping,
    MutableMapping: check_mapping,
    None: check_none,
    collections.abc.Mapping: check_mapping,
    collections.abc.MutableMapping: check_mapping,
    Sequence: check_sequence,
    collections.abc.Sequence: check_sequence,
    collections.abc.Set: check_set,
    set: check_set,
    Set: check_set,
    TextIO: check_io,
    tuple: check_tuple,
    Tuple: check_tuple,
    type: check_class,
    Type: check_class,
    Union: check_union,
    # On some versions of Python, these may simply be re-exports from "typing",
    # but exactly which Python versions is subject to change.
    # It's best to err on the safe side and just always specify these.
    typing_extensions.Literal: check_literal,
    typing_extensions.LiteralString: check_literal_string,
    typing_extensions.Self: check_self,
    typing_extensions.TypeGuard: check_typeguard,
}
if sys.version_info >= (3, 10):
    origin_type_checkers[types.UnionType] = check_uniontype
    origin_type_checkers[typing.TypeGuard] = check_typeguard

if sys.version_info >= (3, 11):
    origin_type_checkers.update(
        {typing.LiteralString: check_literal_string, typing.Self: check_self}
    )

if sys.version_info >= (3, 12):
    type_alias_types = (typing_extensions.TypeAliasType, typing.TypeAliasType)
else:
    type_alias_types = (typing_extensions.TypeAliasType,)


def builtin_checker_lookup(
    origin_type: Any,
    args: tuple[Any, ...],
    extras: tuple[Any, ...],
) -> TypeCheckerCallable | None:
    checker = origin_type_checkers.get(origin_type)
    if checker is not None:
        return checker
    if is_typeddict(origin_type):
        return check_typed_dict
    if isclass(origin_type) and issubclass(origin_type, Tuple):  # type: ignore[arg-type]
        return check_tuple
    if isclass(origin_type) and issubclass(origin_type, IO):
        return check_io
    if (
        isfunction(origin_type)
        and getattr(origin_type, "__module__", None) == "typing"
        and getattr(origin_type, "__qualname__", "").startswith("NewType.")
        and hasattr(origin_type, "__supertype__")
    ):
        return check_newtype
    if isclass(origin_type) and hasattr(origin_type, "__supertype__"):
        # Python 3.10+ NewType is a class with __supertype__
        return check_newtype
    if isinstance(origin_type, TypeVar):
        return check_typevar
    if origin_type.__class__ is ParamSpec:
        return check_paramspec
    return None


checker_lookup_functions.append(builtin_checker_lookup)


@overload
def check_type(
    value: object,
    expected_type: type[T],
    *,
    forward_ref_policy: ForwardRefPolicy = ...,
    typecheck_fail_callback: TypeCheckFailCallback | None = ...,
    collection_check_strategy: CollectionCheckStrategy = ...,
) -> T: ...


@overload
def check_type(
    value: object,
    expected_type: Any,
    *,
    forward_ref_policy: ForwardRefPolicy = ...,
    typecheck_fail_callback: TypeCheckFailCallback | None = ...,
    collection_check_strategy: CollectionCheckStrategy = ...,
) -> Any: ...


def check_type(
    value: object,
    expected_type: Any,
    *,
    forward_ref_policy: ForwardRefPolicy = TypeCheckConfiguration().forward_ref_policy,
    typecheck_fail_callback: TypeCheckFailCallback | None = (
        TypeCheckConfiguration().typecheck_fail_callback
    ),
    collection_check_strategy: CollectionCheckStrategy = (
        TypeCheckConfiguration().collection_check_strategy
    ),
) -> Any:
    """
    Ensure that ``value`` matches ``expected_type``.

    The types from the :mod:`typing` module do not support :func:`isinstance` or
    :func:`issubclass` so a number of type specific checks are required. This function
    knows which checker to call for which type.

    This function wraps :func:`~.check_type_internal` in the following ways:

    * Respects type checking suppression (:func:`~.suppress_type_checks`)
    * Forms a :class:`~.TypeCheckMemo` from the current stack frame
    * Calls the configured type check fail callback if the check fails

    Note that this function is independent of the globally shared configuration in
    :data:`typeguard.config`. This means that usage within libraries is safe from being
    affected configuration changes made by other libraries or by the integrating
    application. Instead, configuration options have the same default values as their
    corresponding fields in :class:`TypeCheckConfiguration`.

    :param value: value to be checked against ``expected_type``
    :param expected_type: a class or generic type instance, or a tuple of such things
    :param forward_ref_policy: see :attr:`TypeCheckConfiguration.forward_ref_policy`
    :param typecheck_fail_callback:
        see :attr`TypeCheckConfiguration.typecheck_fail_callback`
    :param collection_check_strategy:
        see :attr:`TypeCheckConfiguration.collection_check_strategy`
    :return: ``value``, unmodified
    :raises TypeCheckError: if there is a type mismatch

    """
    if type(expected_type) is tuple:
        expected_type = Union[expected_type]

    config = TypeCheckConfiguration(
        forward_ref_policy=forward_ref_policy,
        typecheck_fail_callback=typecheck_fail_callback,
        collection_check_strategy=collection_check_strategy,
    )

    if _suppression.type_checks_suppressed or expected_type is Any:
        return value

    frame = sys._getframe(1)
    memo = TypeCheckMemo(frame.f_globals, frame.f_locals, config=config)
    try:
        check_type_internal(value, expected_type, memo)
    except TypeCheckError as exc:
        exc.append_path_element(qualified_name(value, add_class_prefix=True))
        if config.typecheck_fail_callback:
            config.typecheck_fail_callback(exc, memo)
        else:
            raise

    return value