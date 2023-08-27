from utils import *
import base64
import time


def chat_completion(bot_backend: BotBackend):
    model_choice = bot_backend.gpt_model_choice
    config = bot_backend.config
    kwargs_for_chat_completion = bot_backend.kwargs_for_chat_completion

    assert config['model'][model_choice]['available'], f"{model_choice} is not available for you API key"

    response = openai.ChatCompletion.create(**kwargs_for_chat_completion)
    return response


def add_function_response_to_bot_history(content_to_display, history, unique_id):
    images, text = [], []

    # terminal output
    error_occurred = False
    for mark, out_str in content_to_display:
        if mark in ('stdout', 'execute_result_text', 'display_text'):
            text.append(out_str)
        elif mark in ('execute_result_png', 'execute_result_jpeg', 'display_png', 'display_jpeg'):
            if 'png' in mark:
                images.append(('png', out_str))
            else:
                images.append(('jpg', out_str))
        elif mark == 'error':
            text.append(delete_color_control_char(out_str))
            error_occurred = True
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


def parse_response(chunk, history, bot_backend: BotBackend):
    """
    :return: history, whether_exit
    """
    function_dict = bot_backend.jupyter_kernel.available_functions

    whether_exit = False
    if chunk['choices']:
        delta = chunk['choices'][0]['delta']
        if 'role' in delta:
            bot_backend.set_assistant_role_name(assistant_role_name=delta['role'])
        if 'content' in delta:
            if delta['content'] is not None:
                # null value of content often occur in function call:
                #     {
                #       "role": "assistant",
                #       "content": null,
                #       "function_call": {
                #         "name": "python",
                #         "arguments": ""
                #       }
                #     }
                bot_backend.add_content(content=delta.get('content', ''))
                history[-1][1] = bot_backend.content

        if 'function_call' in delta:
            if 'name' in delta['function_call']:
                bot_backend.set_function_name(function_name=delta['function_call']['name'])
                bot_backend.copy_current_bot_history(bot_history=history)
                if bot_backend.function_name not in function_dict:
                    history.append(
                        [
                            None,
                            f'GPT attempted to call a function that does '
                            f'not exist: {bot_backend.function_name}\n '
                        ]
                    )
                    whether_exit = True

                    return history, whether_exit

            if 'arguments' in delta['function_call']:
                bot_backend.add_function_args_str(function_args_str=delta['function_call']['arguments'])

                if bot_backend.function_name == 'python':  # handle hallucinatory function calls
                    '''
                    In practice, we have noticed that GPT, especially GPT-3.5, may occasionally produce hallucinatory
                    function calls. These calls involve a non-existent function named `python` with arguments consisting 
                    solely of raw code text (not a JSON format).
                    '''
                    temp_code_str = bot_backend.function_args_str
                    bot_backend.update_display_code_block(
                        display_code_block="\n🔴Working:\n```python\n{}\n```".format(temp_code_str)
                    )
                    history = copy.deepcopy(bot_backend.bot_history)
                    history[-1][1] += bot_backend.display_code_block
                else:
                    temp_code_str = parse_json(function_args=bot_backend.function_args_str, finished=False)
                    if temp_code_str is not None:
                        bot_backend.update_display_code_block(
                            display_code_block="\n🔴Working:\n```python\n{}\n```".format(
                                temp_code_str
                            )
                        )
                        history = copy.deepcopy(bot_backend.bot_history)
                        history[-1][1] += bot_backend.display_code_block

        if chunk['choices'][0]['finish_reason'] is not None:
            if bot_backend.content:
                bot_backend.add_gpt_response_content_message()

            bot_backend.update_finish_reason(finish_reason=chunk['choices'][0]['finish_reason'])
            if bot_backend.finish_reason == 'function_call':
                try:
                    if bot_backend.function_name == 'python':
                        code_str = bot_backend.function_args_str
                    else:
                        code_str = parse_json(function_args=bot_backend.function_args_str, finished=True)
                        if code_str is None:
                            raise json.JSONDecodeError
                    bot_backend.update_display_code_block(
                        display_code_block="\n🟢Working:\n```python\n{}\n```".format(code_str)
                    )
                    history = copy.deepcopy(bot_backend.bot_history)
                    history[-1][1] += bot_backend.display_code_block

                    # function response
                    text_to_gpt, content_to_display = function_dict[
                        bot_backend.function_name
                    ](code_str)

                    # add function call to conversion
                    bot_backend.add_function_call_response_message(function_response=text_to_gpt, save_tokens=True)

                    add_function_response_to_bot_history(
                        content_to_display=content_to_display, history=history, unique_id=bot_backend.unique_id
                    )

                except json.JSONDecodeError:
                    history.append(
                        [None, f"GPT generate wrong function args: {bot_backend.function_args_str}"]
                    )
                    whether_exit = True
                    return history, whether_exit

                except Exception as e:
                    history.append([None, f'Backend error: {e}'])
                    whether_exit = True
                    return history, whether_exit
            bot_backend.reset_gpt_response_log_values(exclude=['finish_reason'])

    return history, whether_exit
