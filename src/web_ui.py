from utils import *
import gradio as gr
import shutil

gpt_results = {
    "assistant_role_name": "",
    "content": "",
    "function_name": None,
    "function_args_str": "",
    "display_code_block": "",
    "finish_reason": "stop",
    "parser_wait": 5,
    "content_history": None
}

model = "GPT-3.5"

revocable_files = []


def switch_to_gpt4(whether_switch):
    global model
    if whether_switch:
        model = "GPT-4"
    else:
        model = "GPT-3.5"


def add_text(history: List, text: str):
    global gpt_results
    revocable_files.clear()
    history = history + [(text, None)]
    conversation.append(
        {'role': 'user', 'content': text}
    )
    gpt_results['finish_reason'] = 'new_input'
    return history, gr.update(value="", interactive=False)


def add_file(history: List, file):
    path = file.name
    filename = os.path.basename(path)
    shutil.copy(path, 'work_dir')
    bot_conversation = [f'📁[{filename}]', None]
    gpt_conversation = {'role': 'system', 'content': f'User uploaded a file: {filename}'}
    history.append(bot_conversation)
    conversation.append(gpt_conversation)
    revocable_files.append(
        {
            'bot_conversation': bot_conversation,
            'gpt_conversation': gpt_conversation
        }
    )
    return history


def undo_upload_file(history: List):
    if revocable_files:
        file = revocable_files[-1]
        bot_conversation = file['bot_conversation']
        gpt_conversation = file['gpt_conversation']
        assert history[-1] == bot_conversation
        del history[-1]
        assert conversation[-1] is gpt_conversation
        del conversation[-1]
        del revocable_files[-1]

    if revocable_files:
        return history, gr.Button.update(interactive=True)
    else:
        return history, gr.Button.update(interactive=False)


def bot(history: List):
    global gpt_results

    while gpt_results['finish_reason'] in ('new_input', 'function_call'):
        if history[-1][0] is None:
            history.append(
                [None, ""]
            )
        else:
            history[-1][1] = ""

        response = chat_completion(model_choice=model)
        for chunk in response:
            history, weather_exit = parse_response(
                chunk=chunk,
                history=history,
                gpt_results=gpt_results,
                function_dict=available_functions
            )
            yield history
            if weather_exit:
                exit(-1)

    yield history


with gr.Blocks(theme=gr.themes.Base()) as block:
    """
    Reference: https://www.gradio.app/guides/creating-a-chatbot-fast
    """
    chatbot = gr.Chatbot([], elem_id="chatbot").style(height=750)

    with gr.Row():
        with gr.Column(scale=0.85):
            text_box = gr.Textbox(
                show_label=False,
                placeholder="Enter text and press enter, or upload a file",
            ).style(container=False)
        with gr.Column(scale=0.15, min_width=0):
            file_upload_button = gr.UploadButton("📁", file_types=['file'])

    with gr.Row(equal_height=True):
        with gr.Column(scale=0.85):
            check_box = gr.Checkbox(label="Using GPT-4", interactive=config['model']['GPT-4']['available'])
            check_box.change(fn=switch_to_gpt4, inputs=check_box)
        with gr.Column(scale=0.15, min_width=0):
            undo_file_button = gr.Button(value="↩️Undo upload file", interactive=False)

    txt_msg = text_box.submit(add_text, [chatbot, text_box], [chatbot, text_box], queue=False).then(
        bot, chatbot, chatbot
    )
    txt_msg.then(lambda: gr.update(interactive=True), None, [text_box], queue=False)
    txt_msg.then(lambda: gr.Button.update(interactive=False), None, [undo_file_button], queue=False)
    file_msg = file_upload_button.upload(add_file, [chatbot, file_upload_button], [chatbot], queue=False).then(
        bot, chatbot, chatbot
    )
    file_msg.then(lambda: gr.Button.update(interactive=True), None, [undo_file_button], queue=False)
    undo_file_button.click(fn=undo_upload_file, inputs=[chatbot], outputs=[chatbot, undo_file_button])

block.queue()
block.launch()
