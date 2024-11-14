"""
MODULE
    database.py

DESCRIPTION
    Custom key-value, json based database system.

    Database:
      Database must be initialized from model which type is called T_Model.
      Each database contains ONLY ONE column, name and it's file path.
      After initialization, DB's object is saved into register.
      Register prevents reinitialization and allows quick DB access.
      You can get initialized Database object by calling Database.get_database(name).

      Interface methods:
          - insert(data: T_Model) -> str
            Inserts new row to database, returns provided key.
          - update(key: str, changes: dict[str, Any], iter_append: bool = False, iter_pop: bool = True)
            Updates specified in changes parameter values. Append/pop from iterable if flag is set.
          - get(key: str) -> T_Model
            Returns T_Model object with data from database.
          - increment(key: str, column_name: str) -> bool
            Increment value of number-like field.
          - decrement(key: str, column_name: str) -> bool
            Decrement value of number-like field.
          - get_all_models() -> List[T_Model]
            Returns list of all models saved in database.
          - get_all_keys() -> List[str]
            Returns list of all keys saved in database.

  Defined databases:
      users_db, rooms_db, sessions_db

"""
from modules.paths import Path
from modules import timestamp
from modules.logs import Log

from typing import Any, List, Iterable, Type, Generic, TypeVar, TYPE_CHECKING
from dataclasses import dataclass, asdict
import hashlib
import uuid

if TYPE_CHECKING:
    from dataclasses import _DataclassT

import json


NOT_REQUIRED = "_NOTREQ"
KEY_AS_UUID4 = "_UUID4KEY"
EXACT_KEY = lambda key: f"_EXACT:{key}"
UNDEFINED_DEFAULT_VALUE = NOT_REQUIRED
SET_AFTER_INIT = "_SET_AFTER_INIT"
T_Model = TypeVar("T_Model")


class KeyNotFound(Exception):
    """
    Exception raised when provided key
    has not been found in database.
    """


class RequiredValueNotProvided(Exception):
    """
    Exception raised when value for required
    column wasn't provided
    """


class DBModel:
    dbs_path: Path = Path("./data/")

    @staticmethod
    def model(
        name: str,
        key_provider: str,
        file_path: str = None,
        allow_invalid_values: bool = None,
        dump_on_error: bool = None
    ) -> "_DataclassT":
        def wrapper(cls):
            nonlocal file_path
            if file_path is None:
                file_path = DBModel.dbs_path / name + ".json"

            nonlocal allow_invalid_values
            if allow_invalid_values is None:
                allow_invalid_values = True

            nonlocal dump_on_error
            if dump_on_error is None:
                dump_on_error = True

            db_model = DBModel(
                name,
                key_provider,
                file_path,
                allow_invalid_values,
                dump_on_error,
                cls
            )
            cls.__dbmodel__ = db_model
            return dataclass(cls)
        return wrapper

    def __call__(self, *args, **kwargs):
        return self.model_cls(*args, **kwargs)

    def __init__(self, name: str, key_provider: str, file_path: str, allow_invalid_values: bool, dump_on_error: bool, model_cls: Type) -> None:
        self.name = name
        self.key_provider = key_provider
        self.file_path = file_path
        self.allow_invalid_values = allow_invalid_values
        self.dump_on_error = dump_on_error

        self.model_cls = model_cls
        self.fields = self.model_cls.__annotations__

    def __repr__(self) -> str:
        model_class_name = self.__class__.__name__
        return f"<DBModel: name={self.name} key_provider={self.key_provider} file_path={self.file_path} model_class_name={model_class_name} allow_invalid_values={self.allow_invalid_values} fields={self.fields}>"


def parse_key_provider(key_provider: str, model) -> str:
    """ Create db_key from model and it's key_provider. """
    if key_provider == KEY_AS_UUID4:
        return uuid.uuid4().hex
    
    if key_provider.startswith("_EXACT:"):
        return key_provider.removeprefix("_EXACT:")

    no_hash = key_provider.startswith("!")
    key_provider = key_provider.removeprefix("!")

    if "+" in key_provider:
        attributes = key_provider.split("+")
        key_seed = ""
        for attr in attributes:
            key_seed += str(getattr(model, attr))
    else:
        key_seed = getattr(model, key_provider)

    if no_hash:
        return key_seed

    return hashlib.sha1(key_seed.encode()).hexdigest()


@dataclass
class Column:
    """
    Representation of single model's key.

    date_join: int = None
    ^^^^^^^^^  ^^^   ^^^^
    name       type_ default
    """
    name: str
    type_: type
    default: Any = UNDEFINED_DEFAULT_VALUE

    def __repr__(self) -> str:
        return f"<Column: name={self.name} type:{self.type_} default:{self.default}>"

    def prepare_value(self, value: Any) -> Any:
        """ Cast value to required type if is not. """
        if value == NOT_REQUIRED or value is None:
            value = self.type_() if self.default == UNDEFINED_DEFAULT_VALUE else self.default
            
        elif not isinstance(value, self.type_):
            value = self.type_(value)

        return value

    def validate(self, value: Any) -> bool:
        """ Check if value's type is same as required. """
        return isinstance(value, self.type_)


class Database(Generic[T_Model]):
    """
    Database must be initialized from DBModel.
    Each database contains ONLY ONE column, name and it's file path.
    After initialization, DB's object is saved into register.
    Register prevents reinitialization and allows quick DB access.
    You can get initialized Database object by calling Database.get_database(name).
    """
    register: dict[str, "Database"] = {}

    @staticmethod
    def get_database(name: str) -> "Database":
        """ Get initialized Database object. """
        if name not in Database.register:
            return None
        return Database.register.get(name)

    def __init__(self, model: T_Model):
        self.__model: T_Model = model.__dbmodel__
        self.name = self.__model.name
        self.filepath = self.__model.file_path
        self.key_provider = self.__model.key_provider
        self.allow_invalid_values = self.__model.allow_invalid_values
        self.dump_on_error = self.__model.dump_on_error
        self.columns: dict[str, Column] = {}

        if self.name in Database.register:
            self = Database.register.get(self.name)
            return

        self.__ensure_db_file()
        self.__build_from_model()
        Database.register[self.name] = self

    def __repr__(self) -> str:
        return f"<DB: name={self.name} keyProvider={self.key_provider} columns={set(self.columns.keys())} file={self.filepath}>"

    def __build_from_model(self) -> None:
        """
        Read and parse all data from DB's model provided at initialization.
        Reads model's properties and turns each key into Column object.
        """
        object_fields = self.__model.fields
        for field_name, field_type in object_fields.items():
            if hasattr(self.__model.model_cls, field_name):
                default_value = getattr(self.__model.model_cls, field_name)
            else:
                default_value = UNDEFINED_DEFAULT_VALUE

            column = Column(field_name, field_type, default_value)
            self.columns[field_name] = column
            
    def __ensure_db_file(self) -> None:
        """ Check and create blank DB file if not exists. """
        if not self.filepath.exists():
            self.filepath.touch()
            self.filepath.save_json_content({})
            return

        try:
            self.__get_db_content()

        except json.JSONDecodeError:
            if not self.dump_on_error:
                raise

            corrupted_content = self.filepath.read()
            dumpfile_content = f"\n\n--- DUMP: {timestamp.generate_timestamp()} ---\n" + corrupted_content
            (self.filepath + ".dump").touch().write(dumpfile_content)
            self.filepath.save_json_content({})

    def __get_db_content(self) -> dict:
        """ Get and return database's file content as dict. """
        return self.filepath.get_json_content()

    def __save_model(self, model: T_Model, db_key: str = None) -> str:
        """
        Write entry to database. If key is not provided,
        new entry will be created with provided key.
        Returns database key.
        """
        if db_key is None:
            db_key = parse_key_provider(self.key_provider, model)

        content = {}
        for column_name, value in asdict(model).items():
            column = self.columns.get(column_name)
            value = column.prepare_value(value)

            if not column.validate(value):
                Log.warn(f"(DB:{self.name}) Value: <{value}> did not pass column")

                if column.default != UNDEFINED_DEFAULT_VALUE:
                    value = column.default
                    Log.error(f"(DB:{self.name}) Replaced <{value}> with default value.")

                elif self.allow_invalid_values:
                    value = column.type_()
                    Log.error(f"(DB:{self.name}) Column: {repr(column)} have no default value. Using type")

                else:
                    Log.error(f"(DB:{self.name}) Column: {repr(column)} have no default value. Invalid values are not allowed. Model will not be saved.")
                    return

            content[column_name] = value

        db_content = self.__get_db_content()
        db_content[db_key] = content
        self.filepath.save_json_content(db_content)
        return db_key
    
    def _migrate(self) -> int:
        """
        Should be called if new column has been added to the model. 
        Adds that column into all existing entries. Column must have default value.
        """
        raw_content = self.__get_db_content()
        new_content = {}
        changes = 0
        
        for db_key, row_db_content in raw_content.items(): 
            for column_name, column_obj in self.columns.items():
                if column_name not in row_db_content:
                    row_db_content[column_name] = column_obj.prepare_value(None)
                    changes += 1
                
            new_content[db_key] = row_db_content
            
        if changes:
            Log.info(f"Migration: {self.name} - Saving updated content with: {changes} updated rows.")
            self.filepath.save_json_content(new_content)
            
        return changes

    def insert(self, data: T_Model) -> str:
        """ Insert new entry to database. Returns key. """
        return self.__save_model(data)

    def update(self, key: str, changes: dict[str, Any] | Any, iter_append: bool = False, iter_pop: bool = False) -> None:
        """
        Update specified keys in entry.
        changes parameter does not have to contain all keys with values
          but only changed ones.

        If iter_append is set to True additional data will be appended
          to the original instead of completely replacing list with new data.

        If iter_pop is set to True value will be popped from current list
          instead of being completely replacing list new data.
        """
        if iter_append and iter_pop:
            Log.error(f"(DB:{self.name}) method called with both iter_append and iter_pop flags!")
            return

        model_object = self.get(key)
        for key_name, value in changes.items():
            if not hasattr(model_object, key_name):
                Log.error(f"(DB:{self.name}) Cannot change value of {key_name} (key not found)")
                continue

            if iter_append:
                current_data = getattr(model_object, key_name)
                if isinstance(current_data, list):
                    value = current_data + [value]
                if isinstance(current_data, dict):
                    value = current_data.update(value)

            if iter_pop:
                current_data = getattr(model_object, key_name)
                if isinstance(current_data, list):
                    if value in current_data:
                        current_data.remove(value)
                        value = current_data
                    else:
                        Log.error(f"(DB:{self.name}) Cannot iter_pop {value} from {key_name} (not found)")
                        return
                if isinstance(current_data, dict):
                    current_data.pop(value)
                    value = current_data
                    

            setattr(model_object, key_name, value)

        self.__save_model(model_object, key)

    def delete(self, key: str) -> None:
        """ Delete key-value pair from database. Raises KeyNotFound. """
        key = str(key)
        db_content = self.__get_db_content()
        if key not in db_content:
            raise KeyNotFound(f"db: {self.name} key: {key}")

        db_content.pop(key)
        self.filepath.save_json_content(db_content)

    def get(self, key: str) -> T_Model:
        """
        Get object from database by it's key.
        Raises KeyNotFound error if key is invalid.
        """
        db_content = self.__get_db_content()
        object_content = db_content.get(str(key))
        if object_content is None:
            raise KeyNotFound(f"db: {self.name} key: {key}")

        model_object = self.__model(**object_content)
        model_object._key = key
        return model_object

    def increment(self, key: str, column_name: str) -> bool:
        """ 
        Increment value of field in database if it is Integer or Float. 
        Returns status. Raises KeyNotFound on invalid column_name or key.
        """
        column = self.columns.get(column_name)
        if not column:
            raise KeyNotFound(f"db: {self.name} column: {column_name}")
          
        model = self.get(key)
        if not model:
            raise KeyNotFound(f"db: {self.name} key: {key}")
        
        value = getattr(model, column_name)
        if not isinstance(value, (int, float)):
            return False
        
        value += 1
        setattr(model, column_name, value)
        self.__save_model(model, key)
        return True

    def decrement(self, key: str, column_name: str) -> bool:
        """ 
        Decrement value of field in database if it is Integer or Float. 
        Returns status. Raises KeyNotFound on invalid column_name or key.
        """
        column = self.columns.get(column_name)
        if not column:
            raise KeyNotFound(f"db: {self.name} column: {column_name}")
          
        model = self.get(key)
        if not model:
            raise KeyNotFound(f"db: {self.name} key: {key}")
        
        value = getattr(model, column_name)
        if not isinstance(value, (int, float)):
            return False
        
        value -= 1
        setattr(model, column_name, value)
        self.__save_model(model, key)
        return True

    def get_all_models(self) -> List[T_Model]:
        """ Get all models saved in database. """
        objects = []
        db_content = self.__get_db_content()
        for key, content in db_content.items():
            model = self.__model(**content)
            model._key = key
            objects.append(model)

        return objects

    def get_all_keys(self) -> List[str]:
        """ Get all keys saved in database. """
        return list(self.__get_db_content().keys())
