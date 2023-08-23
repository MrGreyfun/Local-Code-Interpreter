from bot_backend import *
import gradio as gr
import shutil


def switch_to_gpt4(whether_switch):
    global bot_backend_log
    if whether_switch:
        bot_backend_log.update_gpt_model_choice("GPT-4")
    else:
        bot_backend_log.update_gpt_model_choice("GPT-3.5")


def add_text(history, text: str):
    global bot_backend_log
    conversation = bot_backend_log.conversation
    revocable_files = bot_backend_log.revocable_files
    gpt_api_log = bot_backend_log.gpt_api_log

    revocable_files.clear()
    history = history + [(text, None)]
    conversation.append(
        {'role': 'user', 'content': text}
    )
    gpt_api_log['finish_reason'] = 'new_input'

    return history, gr.update(value="", interactive=False)


def add_file(history, file):
    global bot_backend_log
    revocable_files = bot_backend_log.revocable_files
    conversation = bot_backend_log.conversation
    path = file.name
    filename = os.path.basename(path)

    shutil.copy(path, bot_backend_log.jupyter_work_dir)

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


def undo_upload_file(history):
    global bot_backend_log
    revocable_files = bot_backend_log.revocable_files
    conversation = bot_backend_log.conversation

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


def restart(history):
    global bot_backend_log
    history.clear()
    return (
        history,
        gr.Textbox.update(value="", interactive=False),
        gr.Button.update(interactive=False),
        gr.Button.update(interactive=False),
        gr.Button.update(interactive=False)
    )


def bot(history):
    global bot_backend_log
    gpt_api_log = bot_backend_log.gpt_api_log

    while gpt_api_log['finish_reason'] in ('new_input', 'function_call'):
        if history[-1][0] is None:
            history.append(
                [None, ""]
            )
        else:
            history[-1][1] = ""

        response = chat_completion(bot_backend_log=bot_backend_log)
        for chunk in response:
            history, weather_exit = parse_response(
                chunk=chunk,
                history=history,
                bot_backend_log=bot_backend_log,
                function_dict=bot_backend_log.jupyter_kernel.available_functions
            )
            yield history
            if weather_exit:
                exit(-1)

    yield history


if __name__ == '__main__':
    bot_backend_log = BotBackendLog()
    config = bot_backend_log.config

    with gr.Blocks(theme=gr.themes.Base()) as block:
        """
        Reference: https://www.gradio.app/guides/creating-a-chatbot-fast
        """
        # UI components
        chatbot = gr.Chatbot([], elem_id="chatbot", label="Local Code Interpreter", height=750)
        with gr.Row():
            with gr.Column(scale=0.85):
                text_box = gr.Textbox(
                    show_label=False,
                    placeholder="Enter text and press enter, or upload a file",
                    container=False
                )
            with gr.Column(scale=0.15, min_width=0):
                file_upload_button = gr.UploadButton("📁", file_types=['file'])

        with gr.Row(equal_height=True):
            with gr.Column(scale=0.7):
                check_box = gr.Checkbox(label="Using GPT-4", interactive=config['model']['GPT-4']['available'])
                check_box.change(fn=switch_to_gpt4, inputs=check_box)
            with gr.Column(scale=0.15, min_width=0):
                restart_button = gr.Button(value='🔄 Restart')
            with gr.Column(scale=0.15, min_width=0):
                undo_file_button = gr.Button(value="↩️Undo upload file", interactive=False)

        # Components function binding
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

        restart_button.click(
            fn=restart, inputs=[chatbot],
            outputs=[chatbot, text_box, restart_button, file_upload_button, undo_file_button]
        ).then(
            fn=bot_backend_log.restart, inputs=None, outputs=None, queue=False
        ).then(
            fn=lambda: (gr.Textbox.update(interactive=True), gr.Button.update(interactive=True),
                        gr.Button.update(interactive=True)),
            inputs=None, outputs=[text_box, restart_button, file_upload_button], queue=False
        )

    block.queue()
    block.launch(inbrowser=True)
