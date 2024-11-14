from modules.tui import style

from dataclasses import dataclass, field
from collections.abc import Callable
from getpass import getpass
from typing import Any
import string


CHARSET_ALL = string.printable
CHARSET_DIGITS = string.digits


@dataclass
class Prompt:
    question: str
    allowed_chars: str = CHARSET_ALL
    allowed_answers: list[str] = field(default_factory=list)
    max_len: int = 0
    min_len: int = 0
    is_password: bool = False
    converter: Callable | None = None
    validator: Callable | None = None
    
    def __post_init__(self) -> None:
        if self.max_len < 0 or self.min_len > self.max_len and self.max_len > 0:
            raise ValueError("Invalid expected prompt length")

    def ask(self) -> Any:
        print(style.style_input_question(self.question))
        answer = None
        
        while True:
            if self.is_password:
                answer = getpass(style.prompt_password_line)
            else:
                answer = input(style.prompt_line)
            
            try:
                if self.validate(answer):
                    print(style.prompt_end + "\n")
                    return self.process_answer(answer)
            except ValueError as err:
                print(style.style_input_error(str(err)))
            
    def validate(self, value: str | None) -> bool:
        if value is None:
            return False
        
        for char in value:
            if char not in self.allowed_chars:
                raise ValueError(f"Illegal character: {char}")
            
        if len(value) < self.min_len:
            raise ValueError(f"Answer is too short (at least {self.min_len} characters expected)")
        
        if self.max_len > 0 and len(value) > self.max_len:
            raise ValueError(f"Answer is too long (up to {self.max_len} characters expected)")
        
        if self.allowed_answers and value not in self.allowed_answers:
            raise ValueError(f"Answer must be one of: {', '.join(self.allowed_answers)}")
        
        if self.validator:
            self.validator(value)
        
        return True
        
    def process_answer(self, answer: str) -> Any:
        if self.converter:
            return self.converter(answer)
        return answer


@dataclass
class CheckBox:
    title: str
    options: dict[Any, str]  #  (returned) id : DisplayValue

    def __post_init__(self) -> None:
        self.values = {i: val for i, val in enumerate(self.options.keys(), 1)}
        self.checkboxes = {i: val for i, val in enumerate(self.options.values(), 1)}

    def ask(self) -> Any:
        print(style.style_input_question(self.title))
        
        for i, name in self.checkboxes.items():
            print(style.style_checkbox_value(i, name))
            
        print("│")
        answer = None
        
        while True:
            answer = input(style.prompt_line)
            
            try:
                if self.validate(answer):
                    print(style.prompt_end + "\n")
                    return self.process_answer(answer)
            except ValueError as err:
                print(style.style_input_error(str(err)))
            
    def validate(self, answer: str) -> bool:
        if not answer.isnumeric():
            raise ValueError("Expected numeric value.")
        
        answer = int(answer)
        
        if answer not in self.values.keys():
            raise ValueError("Invalid value.")
        
        return True
    
    def process_answer(self, answer: str) -> Any:
        return self.values.get(int(answer))
        
        