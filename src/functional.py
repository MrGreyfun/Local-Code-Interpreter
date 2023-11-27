from bot_backend import *
import base64
import time
import tiktoken
from notebook_serializer import add_code_cell_error_to_notebook, add_image_to_notebook, add_code_cell_output_to_notebook

context_window_per_model = {
    'gpt-4-1106-preview': 128000,
    'gpt-4': 8192,
    'gpt-4-32k': 32768,
    'gpt-4-0613	': 8192,
    'gpt-4-32k-0613': 32768,
    'gpt-3.5-turbo-1106': 16385,
    'gpt-3.5-turbo': 4096,
    'gpt-3.5-turbo-16k': 16385,
    'gpt-3.5-turbo-0613': 4096,
}

def get_conversation_slice(conversation, model):
    encoder = tiktoken.encoding_for_model(model)
    count_tokens = lambda txt: len(encoder.encode(txt))
    first_message_i = -1
    nb_tokens = count_tokens(conversation[0]['content'])
    for message in conversation[1::-1]:
        nb_tokens += count_tokens(message['content'])
        if nb_tokens > context_window_per_model[model]:
            break
        first_message_i -= 1
    sliced_conv = [conversation[0]] + conversation[first_message_i:-1]
    # print(json.dumps(sliced_conv, indent=1))
    # print("================================")
    # count_tokens_in_conv = lambda conv : sum([count_tokens(message['content']) for message in conv])
    # print("actual_conv_nb_tokens:", count_tokens_in_conv(conversation))
    # print("sliced conv tokens:", count_tokens_in_conv(sliced_conv))
    # print("context window:", context_window_per_model[model])
    # print("model name:", model)
    return sliced_conv

def chat_completion(bot_backend: BotBackend):
    model_choice = bot_backend.gpt_model_choice
    config = bot_backend.config
    # print(json.dumps(config, indent=1))
    model_name = config['model'][model_choice]['model_name']
    kwargs_for_chat_completion = bot_backend.kwargs_for_chat_completion
    kwargs_for_chat_completion['messages'] = get_conversation_slice(kwargs_for_chat_completion['messages'], model_name)

    assert config['model'][model_choice]['available'], f"{model_choice} is not available for your API key"

    response = openai.ChatCompletion.create(**kwargs_for_chat_completion)
    return response


def add_function_response_to_bot_history(content_to_display, history, unique_id):
    images, text = [], []


    # terminal output
    error_occurred = False

    for mark, out_str in content_to_display:
        if mark in ('stdout', 'execute_result_text', 'display_text'):
            text.append(out_str)
            add_code_cell_output_to_notebook(out_str)
        elif mark in ('execute_result_png', 'execute_result_jpeg', 'display_png', 'display_jpeg'):
            if 'png' in mark:
                images.append(('png', out_str))
                add_image_to_notebook(out_str, 'image/png')
            else:
                add_image_to_notebook(out_str, 'image/jpeg')
                images.append(('jpg', out_str))
        elif mark == 'error':
            # Set output type to error
            text.append(delete_color_control_char(out_str))
            error_occurred = True
            add_code_cell_error_to_notebook(out_str)
    text = '\n'.join(text).strip('\n')
    if error_occurred:
        history.append([None, f'❌Terminal output:\n```shell\n\n{text}\n```'])
    else:
        history.append([None, f'✔️Terminal output:\n```shell\n{text}\n```'])

    # image output
    for filetype, img in images:
        image_bytes = base64.b64decode(img)
        temp_path = f'cache/temp_{unique_id}'
        if not os.path.exists(temp_path):
            os.mkdir(temp_path)
        path = f'{temp_path}/{hash(time.time())}.{filetype}'
        with open(path, 'wb') as f:
            f.write(image_bytes)
        history.append(
            [
                None,
                f'<img src=\"file={path}\" style=\'width: 600px; max-width:none; max-height:none\'>'
            ]
        )


def parse_json(function_args: str, finished: bool):
    """
    GPT may generate non-standard JSON format string, which contains '\n' in string value, leading to error when using
    `json.loads()`.
    Here we implement a parser to extract code directly from non-standard JSON string.
    :return: code string if successfully parsed otherwise None
    """
    parser_log = {
        'met_begin_{': False,
        'begin_"code"': False,
        'end_"code"': False,
        'met_:': False,
        'met_end_}': False,
        'met_end_code_"': False,
        "code_begin_index": 0,
        "code_end_index": 0
    }
    try:
        for index, char in enumerate(function_args):
            if char == '{':
                parser_log['met_begin_{'] = True
            elif parser_log['met_begin_{'] and char == '"':
                if parser_log['met_:']:
                    if finished:
                        parser_log['code_begin_index'] = index + 1
                        break
                    else:
                        if index + 1 == len(function_args):
                            return ''
                        else:
                            temp_code_str = function_args[index + 1:]
                            if '\n' in temp_code_str:
                                return temp_code_str.strip('\n')
                            else:
                                return json.loads(function_args + '"}')['code']
                elif parser_log['begin_"code"']:
                    parser_log['end_"code"'] = True
                else:
                    parser_log['begin_"code"'] = True
            elif parser_log['end_"code"'] and char == ':':
                parser_log['met_:'] = True
            else:
                continue
        if finished:
            for index, char in enumerate(function_args[::-1]):
                back_index = -1 - index
                if char == '}':
                    parser_log['met_end_}'] = True
                elif parser_log['met_end_}'] and char == '"':
                    parser_log['code_end_index'] = back_index - 1
                    break
                else:
                    continue
            code_str = function_args[parser_log['code_begin_index']: parser_log['code_end_index'] + 1]
            if '\n' in code_str:
                return code_str.strip('\n')
            else:
                return json.loads(function_args)['code']

    except Exception as e:
        return None
    
