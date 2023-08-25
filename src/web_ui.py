from bot_backend import *
import gradio as gr
import shutil


def initialization(state_dict):
    if not os.path.exists('cache'):
        os.mkdir('cache')
    if state_dict["bot_backend_log"] is None:
        state_dict["bot_backend_log"] = BotBackendLog()


def get_bot_backend_log(state_dict):
    return state_dict["bot_backend_log"]


def switch_to_gpt4(state_dict, whether_switch):
    bot_backend_log = get_bot_backend_log(state_dict)
    if whether_switch:
        bot_backend_log.update_gpt_model_choice("GPT-4")
    else:
        bot_backend_log.update_gpt_model_choice("GPT-3.5")
    return state_dict


def add_text(state_dict, history, text: str):
    bot_backend_log = get_bot_backend_log(state_dict)
    conversation = bot_backend_log.conversation
    revocable_files = bot_backend_log.revocable_files
    gpt_api_log = bot_backend_log.gpt_api_log

    revocable_files.clear()
    history = history + [(text, None)]
    conversation.append(
        {'role': 'user', 'content': text}
    )
    gpt_api_log['finish_reason'] = 'new_input'

    return state_dict, history, gr.update(value="", interactive=False)


def add_file(state_dict, history, file):
    bot_backend_log = get_bot_backend_log(state_dict)
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
            'gpt_conversation': gpt_conversation,
            'path': os.path.join(bot_backend_log.jupyter_work_dir, filename)
        }
    )
    return state_dict, history


def undo_upload_file(state_dict, history):
    bot_backend_log = get_bot_backend_log(state_dict)
    revocable_files = bot_backend_log.revocable_files
    conversation = bot_backend_log.conversation

    if revocable_files:
        file = revocable_files[-1]
        bot_conversation = file['bot_conversation']
        gpt_conversation = file['gpt_conversation']
        path = file['path']
        assert history[-1] == bot_conversation
        del history[-1]
        assert conversation[-1] is gpt_conversation
        del conversation[-1]
        os.remove(path)
        del revocable_files[-1]

    if revocable_files:
        return state_dict, history, gr.Button.update(interactive=True)
    else:
        return state_dict, history, gr.Button.update(interactive=False)


def refresh_file_display(state_dict):
    bot_backend_log = get_bot_backend_log(state_dict)
    work_dir = bot_backend_log.jupyter_work_dir
    filenames = os.listdir(work_dir)
    paths = []
    for filename in filenames:
        paths.append(
            os.path.join(work_dir, filename)
        )
    return paths


def restart_ui(history):
    history.clear()
    return (
        history,
        gr.Textbox.update(value="", interactive=False),
        gr.Button.update(interactive=False),
        gr.Button.update(interactive=False),
        gr.Button.update(interactive=False)
    )


def restart_bot_backend_log(state_dict):
    bot_backend_log = get_bot_backend_log(state_dict)
    bot_backend_log.restart()
    return state_dict


def bot(state_dict, history):
    bot_backend_log = get_bot_backend_log(state_dict)
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
    config = get_config()
    with gr.Blocks(theme=gr.themes.Base()) as block:
        """
        Reference: https://www.gradio.app/guides/creating-a-chatbot-fast
        """
        # UI components
        state = gr.State(value={"bot_backend_log": None})
        with gr.Tab("Chat"):
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
                    check_box.change(fn=switch_to_gpt4, inputs=[state, check_box], outputs=[state])
                with gr.Column(scale=0.15, min_width=0):
                    restart_button = gr.Button(value='🔄 Restart')
                with gr.Column(scale=0.15, min_width=0):
                    undo_file_button = gr.Button(value="↩️Undo upload file", interactive=False)
        with gr.Tab("Files"):
            file_output = gr.Files()

        # Components function binding
        txt_msg = text_box.submit(add_text, [state, chatbot, text_box], [state, chatbot, text_box], queue=False).then(
            bot, [state, chatbot], chatbot
        )
        txt_msg.then(fn=refresh_file_display, inputs=[state], outputs=[file_output])
        txt_msg.then(lambda: gr.update(interactive=True), None, [text_box], queue=False)
        txt_msg.then(lambda: gr.Button.update(interactive=False), None, [undo_file_button], queue=False)

        file_msg = file_upload_button.upload(
            add_file, [state, chatbot, file_upload_button], [state, chatbot], queue=False
        ).then(
            bot, [state, chatbot], chatbot
        )
        file_msg.then(lambda: gr.Button.update(interactive=True), None, [undo_file_button], queue=False)
        file_msg.then(fn=refresh_file_display, inputs=[state], outputs=[file_output])

        undo_file_button.click(
            fn=undo_upload_file, inputs=[state, chatbot], outputs=[state, chatbot, undo_file_button]
        ).then(
            fn=refresh_file_display, inputs=[state], outputs=[file_output]
        )

        restart_button.click(
            fn=restart_ui, inputs=[chatbot],
            outputs=[chatbot, text_box, restart_button, file_upload_button, undo_file_button]
        ).then(
            fn=restart_bot_backend_log, inputs=[state], outputs=[state], queue=False
        ).then(
            fn=refresh_file_display, inputs=[state], outputs=[file_output]
        ).then(
            fn=lambda: (gr.Textbox.update(interactive=True), gr.Button.update(interactive=True),
                        gr.Button.update(interactive=True)),
            inputs=None, outputs=[text_box, restart_button, file_upload_button], queue=False
        )

        block.load(fn=initialization, inputs=[state])

    block.queue()
    block.launch(inbrowser=True)
