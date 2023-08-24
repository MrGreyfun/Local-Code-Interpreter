import json
import openai
import os
from jupyter_backend import *

functions = [
    {
        "name": "execute_code",
        "description": "This function allows you to execute Python code and retrieve the terminal output. If the code "
                       "generates image output, the function will return the text '[image]'. The code is sent to a "
                       "Jupyter kernel for execution. The kernel will remain active after execution, retaining all "
                       "variables in memory.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The code text"
                }
            },
            "required": ["code"],
        }
    }
]

system_msg = '''You are an AI code interpreter.
Your goal is to help users do a variety of jobs by executing Python code.

You should:
1. Comprehend the user's requirements carefully & to the letter. 
2. Give a brief description for what you plan to do & call the execute_code function to run code
3. Provide results analysis based on the execution output. 
4. If error occurred, try to fix it.

Note: If the user uploads a file, you will receive a system message "User uploaded a file: filename". Use the filename as the path in the code. '''


def get_config():
    with open('config.json') as f:
        config = json.load(f)
    return config


def config_openai_api(api_type, api_base, api_version, api_key):
    openai.api_type = api_type
    openai.api_base = api_base
    openai.api_version = api_version
    openai.api_key = api_key


class BotBackendLog:
    def __init__(self):
        self.unique_id = hash(id(self))
        self.jupyter_work_dir = f'cache/work_dir_{self.unique_id}'
        self.jupyter_kernel = JupyterKernel(work_dir=self.jupyter_work_dir)
        self.gpt_model_choice = "GPT-3.5"
        self.revocable_files = []
        self._init_conversation()
        self._init_api_config()
        self._init_kwargs_for_chat_completion()
        self._init_gpt_api_log()

    def _init_conversation(self):
        first_system_msg = {'role': 'system', 'content': system_msg}
        if hasattr(self, 'conversation'):
            self.conversation.clear()
            self.conversation.append(first_system_msg)
        else:
            self.conversation = [first_system_msg]

    def _init_api_config(self):
        self.config = get_config()
        api_type = self.config['API_TYPE']
        api_base = self.config['API_base']
        api_version = self.config['API_VERSION']
        if self.config['API_KEY']:
            api_key = self.config['API_KEY']
        else:
            api_key = os.getenv('OPENAI_API_KEY')

        config_openai_api(api_type, api_base, api_version, api_key)

    def _init_kwargs_for_chat_completion(self):
        self.kwargs_for_chat_completion = {
            'stream': True,
            'messages': self.conversation,
            'functions': functions,
            'function_call': 'auto'
        }

        model_name = self.config['model'][self.gpt_model_choice]['model_name']

        if self.config['API_TYPE'] == 'azure':
            self.kwargs_for_chat_completion['engine'] = model_name
        else:
            self.kwargs_for_chat_completion['model'] = model_name

    def _init_gpt_api_log(self):
        self.gpt_api_log = {
            "assistant_role_name": "",
            "content": "",
            "function_name": None,
            "function_args_str": "",
            "display_code_block": "",
            "finish_reason": "stop",
            "content_history": None
        }

    def update_gpt_model_choice(self, model_choice):
        self.gpt_model_choice = model_choice
        self._init_kwargs_for_chat_completion()

    def restart(self):
        for filename in os.listdir(self.jupyter_work_dir):
            os.remove(
                os.path.join(self.jupyter_work_dir, filename)
            )
        self.revocable_files.clear()
        self._init_conversation()
        self._init_gpt_api_log()
        self.jupyter_kernel.restart_jupyter_kernel()
