import jupyter_client
import re

# Start a kernel
kernel_manager, kernel_client = jupyter_client.manager.start_new_kernel(kernel_name='python3')


def execute_code_(code):
    msg_id = kernel_client.execute(code)

    # Get the output of the code
    iopub_msg = kernel_client.get_iopub_msg()

    all_output = []
    while True:
        if iopub_msg['msg_type'] == 'stream':
            if iopub_msg['content'].get('name') == 'stdout':
                output = iopub_msg['content']['text']
                all_output.append(('stdout', output))
            iopub_msg = kernel_client.get_iopub_msg()
        elif iopub_msg['msg_type'] == 'execute_result':
            if 'data' in iopub_msg['content']:
                if 'text/plain' in iopub_msg['content']['data']:
                    output = iopub_msg['content']['data']['text/plain']
                    all_output.append(('execute_result_text', output))
                if 'text/html' in iopub_msg['content']['data']:
                    output = iopub_msg['content']['data']['text/html']
                    all_output.append(('execute_result_html', output))
                if 'image/png' in iopub_msg['content']['data']:
                    output = iopub_msg['content']['data']['image/png']
                    all_output.append(('execute_result_png', output))
                if 'image/jpeg' in iopub_msg['content']['data']:
                    output = iopub_msg['content']['data']['image/jpeg']
                    all_output.append(('execute_result_jpeg', output))
            iopub_msg = kernel_client.get_iopub_msg()
        elif iopub_msg['msg_type'] == 'display_data':
            if 'data' in iopub_msg['content']:
                if 'text/plain' in iopub_msg['content']['data']:
                    output = iopub_msg['content']['data']['text/plain']
                    all_output.append(('display_text', output))
                if 'text/html' in iopub_msg['content']['data']:
                    output = iopub_msg['content']['data']['text/html']
                    all_output.append(('display_html', output))
                if 'image/png' in iopub_msg['content']['data']:
                    output = iopub_msg['content']['data']['image/png']
                    all_output.append(('display_png', output))
                if 'image/jpeg' in iopub_msg['content']['data']:
                    output = iopub_msg['content']['data']['image/jpeg']
                    all_output.append(('display_jpeg', output))
            iopub_msg = kernel_client.get_iopub_msg()
        elif iopub_msg['msg_type'] == 'error':
            if 'traceback' in iopub_msg['content']:
                output = '\n'.join(iopub_msg['content']['traceback'])
                all_output.append(('error', output))
            iopub_msg = kernel_client.get_iopub_msg()
        elif iopub_msg['msg_type'] == 'status' and iopub_msg['content'].get('execution_state') == 'idle':
            break
        else:
            iopub_msg = kernel_client.get_iopub_msg()

    return all_output


def delete_color_control_char(string):
    ansi_escape = re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
    return ansi_escape.sub('', string)


def execute_code(code):
    text_to_gpt = []
    content_to_display = execute_code_(code)
    for mark, out_str in content_to_display:
        if mark in ('stdout', 'execute_result_text', 'display_text'):
            text_to_gpt.append(out_str)
        elif mark in ('execute_result_png', 'execute_result_jpeg', 'display_png', 'display_jpeg'):
            text_to_gpt.append('[image]')
        elif mark == 'error':
            text_to_gpt.append(delete_color_control_char(out_str))

    return '\n'.join(text_to_gpt), content_to_display


available_functions = {
    'execute_code': execute_code,
    'python': execute_code
}

# set work dir in jupyter environment
init_code = '''
import os
if not os.path.exists('work_dir'):
    os.mkdir('work_dir')
os.chdir('work_dir')
'''
execute_code_(init_code)


def restart_jupyter_backend():
    global kernel_client, kernel_manager
    kernel_client.shutdown()
    kernel_manager, kernel_client = jupyter_client.manager.start_new_kernel(kernel_name='python3')
    execute_code_(init_code)
