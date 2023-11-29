import nbformat
from nbformat import v4 as nbf
import ansi2html
import os
import json
import argparse

# main code
parser = argparse.ArgumentParser()
parser.add_argument("-n", "--notebook", help="Path to the output notebook", default=None, type=str)
args = parser.parse_args()
nb = nbf.new_notebook()
notebook_path = ""

if args.notebook:
    notebook_path = os.path.join(os.getcwd(), args.notebook)
    base, ext = os.path.splitext(notebook_path)
    if ext.lower() != '.ipynb':
        notebook_path += '.ipynb'
    
    if os.path.isfile(notebook_path):
        with open(notebook_path, 'r') as notebook_file:
            nb = nbformat.read(notebook_file, as_version=4)

def desirialize_notebook_into_conv_history():
    history = []
    for cell in nb['cells']:
        # Handle markdown
        if cell['cell_type'] == 'markdown':
            append_to_history(history, cell['source'], cell)
        # Handle code
        if cell['cell_type'] == 'code':
            append_to_history(history, "```python\n" + cell['source'] + "\n```", cell)
            # Handle outputs
            for output in cell['outputs']:
                # Handle display data
                if output['output_type'] == 'display_data':
                    for mime_type, output_data in output['data'].items():
                        if 'text' in mime_type:
                            append_to_history(history, output_data, cell)
                # Handle error
                if output['output_type'] == 'error':
                    for tracebak in output['traceback']:
                        append_to_history(history, ansi_to_html(tracebak), cell)
    return history

def append_to_history(history, obj, cell):
    is_from_user = 'author' in cell['metadata'] and cell['metadata']['author'] == 'user'
    if is_from_user:
        history.append((obj, None))
    else:
        history.append((None, obj))

def ansi_to_html(ansi_text):
    converter = ansi2html.Ansi2HTMLConverter()
    html_text = converter.convert(ansi_text)
    return html_text

def write_to_notebook():
    if args.notebook:
        with open(notebook_path, 'w', encoding='utf-8') as f:
            nbformat.write(nb, f)

def add_code_cell_to_notebook(code):
    code_cell = nbf.new_code_cell(source=code)
    nb['cells'].append(code_cell)
    write_to_notebook()

def add_code_cell_output_to_notebook(output):
    html_content = ansi_to_html(output)
    cell_output = nbf.new_output(output_type='display_data', data={'text/html': html_content})
    nb['cells'][-1]['outputs'].append(cell_output)
    write_to_notebook()

def add_code_cell_error_to_notebook(error):
    nbf_error_output = nbf.new_output(
        output_type='error',
        ename='Error',
        evalue='Error message',
        traceback=[error]
    )
    nb['cells'][-1]['outputs'].append(nbf_error_output)
    write_to_notebook()

def add_image_to_notebook(image, mime_type):
    image_output = nbf.new_output(output_type='display_data', data={mime_type: image})
    nb['cells'][-1]['outputs'].append(image_output)
    write_to_notebook()

def add_markdown_to_notebook(content, title=None):
    if title:
        content = "##### " + title + ":\n" + content
    markdown_cell = nbf.new_markdown_cell(content)
    nb['cells'].append(markdown_cell)
    write_to_notebook()
